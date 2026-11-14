"""Deterministic release verification, PyPI idempotency planner, and isolated package acceptance gate."""
from __future__ import annotations

import argparse
import ast
import base64
import configparser
import csv
from email.parser import BytesParser
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.error import HTTPError
from urllib.request import Request
import venv
import zipfile

from ._stdlib import safe_path
from .research.sources import controlled_urlopen

PACKAGE = "academic-research-kernel"
DIST_PREFIX = "academic_research_kernel"
SIDECARS = frozenset({"release-manifest.json", "SHA256SUMS", "server.json"})


def require(condition: bool, message: str) -> None:
    """Release gates remain active even under python -O."""
    if not condition:
        raise ValueError(message)


def validate_version_tag(version: str, tag: str) -> tuple[str, str]:
    require(
        isinstance(version, str) and bool(re.fullmatch(r"\d+\.\d+\.\d+", version)),
        "version must be an explicit canonical stable X.Y.Z version",
    )
    require(
        all(str(int(part)) == part for part in version.split(".")),
        "version cannot contain leading zeroes",
    )
    require(tag == f"v{version}", "tag must equal v followed by the expected version")
    return version, tag


def package_filenames(version: str) -> set[str]:
    return {
        f"{DIST_PREFIX}-{version}-py3-none-any.whl",
        f"{DIST_PREFIX}-{version}.tar.gz",
    }


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            encoding="utf-8",
            stderr=subprocess.PIPE,
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"Git source identity unavailable: {args[-1]}") from exc


def _read_literal_version(src_text: str) -> str:
    tree = ast.parse(src_text)
    found = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    require(len(found) == 1, "source _version.py must declare exactly one literal __version__")
    return found[0]


def verify_sll_preserved_files(root: Path) -> dict[str, str]:
    sll_path = root / "SLL-APPLICATION.json"
    require(sll_path.is_file(), "SLL-APPLICATION.json missing from repository root")
    sll = json.loads(sll_path.read_text(encoding="utf-8"))
    lic_path = root / "LICENSE"
    require(lic_path.is_file(), "LICENSE missing from repository root")
    lic_sha = hashlib.sha256(lic_path.read_bytes()).hexdigest()
    require(lic_sha == sll.get("license_sha256"), "LICENSE SHA-256 differs from SLL-APPLICATION.json")
    preserved = sll.get("preserved_mit_files")
    require(isinstance(preserved, dict) and len(preserved) > 0, "SLL-APPLICATION.json preserved_mit_files empty")
    verified: dict[str, str] = {}
    for rel, expected_sha in preserved.items():
        fp = safe_path(root / rel, root=root, must_exist=True)
        actual_sha = hashlib.sha256(fp.read_bytes()).hexdigest()
        require(actual_sha == expected_sha, f"Preserved MIT file hash mismatch: {rel}")
        verified[rel] = actual_sha
    return verified


def validate_target(
    version: str,
    tag: str,
    root: Path,
    expected_commit: str | None = None,
    *,
    require_head: bool = False,
    require_main_ancestry: bool = True,
) -> dict[str, str]:
    validate_version_tag(version, tag)
    tag_ref = f"refs/tags/{tag}"
    require(_git(root, "cat-file", "-t", tag_ref) == "tag", "release tag must be an annotated git tag")
    commit = _git(root, "rev-parse", f"{tag_ref}^{{commit}}")
    tree = _git(root, "rev-parse", f"{commit}^{{tree}}")
    require(
        bool(re.fullmatch(r"[0-9a-f]{40}", commit)) and bool(re.fullmatch(r"[0-9a-f]{40}", tree)),
        "invalid Git commit/tree identity",
    )
    if expected_commit is not None:
        require(commit == expected_commit, "release tag moved or differs from verified target commit")
    if require_main_ancestry:
        anc = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", commit, "origin/main"],
            capture_output=True,
            text=True,
        )
        require(anc.returncode == 0, "release tag commit must already be an ancestor of origin/main")
    ver_blob = _git(root, "show", f"{commit}:src/academic_research_kernel/_version.py")
    require(_read_literal_version(ver_blob) == version, "tagged _version.py differs from expected version")
    if require_head:
        require(_git(root, "rev-parse", "HEAD") == commit, "checkout HEAD differs from release tag commit")
        require(not _git(root, "status", "--porcelain", "--untracked-files=normal"), "release worktree must be clean")
        verify_sll_preserved_files(root)
    return {
        "version": version,
        "tag": tag,
        "commit": commit,
        "tree": tree,
        "tag_object": _git(root, "rev-parse", tag_ref),
    }


def _load_pyproject(source_root: Path) -> dict[str, object]:
    raw = (source_root / "pyproject.toml").read_bytes()
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib.loads(raw.decode("utf-8"))
    import tomli  # type: ignore[import-not-found]

    return tomli.loads(raw.decode("utf-8"))


def _verify_wheel_dist_info(
    files: dict[str, bytes],
    dist_info_prefix: str,
    version: str,
    *,
    source_root: Path | None = None,
) -> None:
    meta_key = f"{dist_info_prefix}METADATA"
    wheel_key = f"{dist_info_prefix}WHEEL"
    ep_key = f"{dist_info_prefix}entry_points.txt"
    rec_key = f"{dist_info_prefix}RECORD"
    for req_k in (meta_key, wheel_key, ep_key, rec_key):
        require(req_k in files, f"wheel missing required dist-info file: {req_k}")

    parsed = BytesParser().parsebytes(files[meta_key])
    require(parsed.get("Name") == PACKAGE and parsed.get("Version") == version, "wheel METADATA Name/Version mismatch")
    lic_expr = (parsed.get("License-Expression") or parsed.get("License") or "").strip()
    require(lic_expr == "LicenseRef-Source-Lineage-1.0", f"wheel METADATA license mismatch: {lic_expr!r}")

    cp = configparser.ConfigParser()
    cp.read_string(files[ep_key].decode("utf-8"))
    require(cp.has_section("console_scripts"), "wheel entry_points.txt missing [console_scripts]")
    actual_scripts = dict(cp.items("console_scripts"))
    require(
        actual_scripts.get("academic-research-kernel") == "academic_research_kernel.cli:main",
        f"wheel console_scripts mismatch: {actual_scripts!r}",
    )

    if source_root is not None and (source_root / "pyproject.toml").is_file():
        pyproj = _load_pyproject(source_root)
        proj = pyproj.get("project") if isinstance(pyproj.get("project"), dict) else {}
        exp_scripts = proj.get("scripts") if isinstance(proj.get("scripts"), dict) else {}
        require(actual_scripts == exp_scripts, f"wheel entry_points.txt {actual_scripts!r} != pyproject scripts {exp_scripts!r}")

        def _norm_spec_clauses(spec_s: str) -> str:
            clauses = [re.sub(r"\s+", "", c).lower() for c in spec_s.split(",") if c.strip()]
            return ",".join(sorted(clauses))

        exp_req_py = _norm_spec_clauses(str(proj.get("requires-python") or ""))
        act_req_py = _norm_spec_clauses(str(parsed.get("Requires-Python") or ""))
        if exp_req_py:
            require(act_req_py == exp_req_py, f"wheel Requires-Python {act_req_py!r} != pyproject {exp_req_py!r}")

        def _norm_req(r_s: str) -> str:
            base, sep, marker = r_s.partition(";")
            m_pkg = re.match(r"^\s*([A-Za-z0-9_.\-]+(?:\[[^\]]*\])?)\s*(.*)$", base)
            if not m_pkg:
                return re.sub(r"\s+", "", r_s).lower()
            pkg_part = re.sub(r"[-_.]+", "-", m_pkg.group(1).strip().lower())
            spec_part = _norm_spec_clauses(m_pkg.group(2))
            marker_part = (";" + re.sub(r"\s+", "", marker).lower()) if sep and marker.strip() else ""
            return f"{pkg_part}{spec_part}{marker_part}"

        req_dists = [_norm_req(str(r)) for r in (parsed.get_all("Requires-Dist") or []) if "; extra ==" not in str(r) and ";extra==" not in re.sub(r"\s+", "", str(r)).lower()]
        exp_deps = [_norm_req(str(d)) for d in (proj.get("dependencies") or [])]
        require(
            sorted(req_dists) == sorted(exp_deps),
            f"wheel core Requires-Dist {sorted(req_dists)!r} != pyproject dependencies {sorted(exp_deps)!r}",
        )

        exp_lic_rels = [str(lf).replace("\\", "/").lstrip("./") for lf in (proj.get("license-files") or [])]
        if exp_lic_rels:
            lic_prefix = f"{dist_info_prefix}licenses/"
            act_lic_files = {
                k[len(lic_prefix):]: v
                for k, v in files.items()
                if k.startswith(lic_prefix)
            }
            require(
                set(act_lic_files) == set(exp_lic_rels),
                f"wheel dist-info/licenses set {sorted(act_lic_files)!r} != pyproject license-files {sorted(exp_lic_rels)!r}",
            )
            for l_rel in exp_lic_rels:
                exp_lb = (source_root / l_rel).read_bytes()
                require(act_lic_files[l_rel] == exp_lb, f"wheel license file bytes mismatch on {l_rel}")

    # Verify RECORD integrity across all wheel files
    seen_rec: set[str] = set()
    reader = csv.reader(io.StringIO(files[rec_key].decode("utf-8")))
    for row in reader:
        require(len(row) == 3, f"malformed wheel RECORD row: {row!r}")
        r_name, r_hash, r_size = row
        require(r_name in files and r_name not in seen_rec, f"invalid or duplicate wheel RECORD entry: {r_name!r}")
        seen_rec.add(r_name)
        if r_name == rec_key:
            require(r_hash == "" and r_size == "", "RECORD self-entry must have empty hash and size")
        else:
            b = files[r_name]
            exp_h = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(b).digest()).decode("ascii").rstrip("=")
            require(r_hash == exp_h and r_size == str(len(b)), f"wheel RECORD digest/size mismatch on {r_name}")
    require(seen_rec == set(files), "wheel RECORD does not cover exact archive file set")


def inspect_artifact(path: Path, version: str, *, source_root: Path | None = None) -> dict[str, object]:
    validate_version_tag(version, f"v{version}")
    require(path.name in package_filenames(version), f"unexpected package filename: {path.name}")
    require(path.is_file() and not path.is_symlink(), f"package must be a regular file: {path}")
    raw_bytes = path.read_bytes()
    sha = hashlib.sha256(raw_bytes).hexdigest()

    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            names = [i.filename for i in infos]
            require(len(names) == len(set(names)), "duplicate wheel archive member")
            require(
                all(((i.external_attr >> 16) & 0o170000) != 0o120000 for i in infos),
                "wheel archive symlinks are forbidden",
            )
            files = {i.filename: zf.read(i.filename) for i in infos if not i.filename.endswith("/")}
        dist_info_prefix = f"{DIST_PREFIX}-{version}.dist-info/"
        _verify_wheel_dist_info(files, dist_info_prefix, version, source_root=source_root)
        ver_key = "academic_research_kernel/_version.py"
        require(ver_key in files and _read_literal_version(files[ver_key].decode("utf-8")) == version, "wheel _version.py mismatch")
        for core_mod in ("__init__.py", "__main__.py", "cli.py", "mcp_server.py", "state_db.py"):
            require(f"academic_research_kernel/{core_mod}" in files, f"wheel missing core module {core_mod}")
        schema_files = [k for k in files if k.startswith("academic_research_kernel/schemas/") and k.endswith(".schema.json")]
        require(len(schema_files) == 26, f"wheel must bundle all 26 schemas, found {len(schema_files)}")
        require(
            any(k.startswith("academic_research_kernel/portable_skills/") and k.endswith("/SKILL.md") for k in files),
            "wheel missing portable SKILL.md",
        )
        if source_root is not None:
            src_pkg = source_root / "src"
            expected_pkg_files = {
                p.relative_to(src_pkg).as_posix(): p.read_bytes()
                for p in src_pkg.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc")
            }
            actual_pkg_files = {k: v for k, v in files.items() if not k.startswith(dist_info_prefix)}
            require(
                set(actual_pkg_files) == set(expected_pkg_files),
                "wheel package member set differs from tagged source tree",
            )
            for rel_k, exp_b in expected_pkg_files.items():
                require(actual_pkg_files[rel_k] == exp_b, f"wheel member bytes differ from tagged source: {rel_k}")
    else:
        with tarfile.open(path, "r:gz") as tf:
            members = tf.getmembers()
            mnames = [m.name for m in members]
            require(len(mnames) == len(set(mnames)), "duplicate sdist archive member")
            require(all(m.isfile() or m.isdir() for m in members), "sdist links or special files are forbidden")
            files = {}
            for m in members:
                if m.isfile():
                    extracted = tf.extractfile(m)
                    require(extracted is not None, f"unreadable sdist member: {m.name}")
                    files[m.name] = extracted.read()
        prefix = f"{DIST_PREFIX}-{version}/"
        pkg_info_key = f"{prefix}PKG-INFO"
        require(pkg_info_key in files, f"sdist missing {pkg_info_key}")
        parsed = BytesParser().parsebytes(files[pkg_info_key])
        require(parsed.get("Name") == PACKAGE and parsed.get("Version") == version, "sdist PKG-INFO Name/Version mismatch")
        for req_rel in (
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "LICENSES/MIT-pre-SLL.txt",
            "server.json",
            "plugin.json",
            "mcp.json",
            "SLL-APPLICATION.json",
            "CHANGELOG.md",
            "uv.lock",
            "src/academic_research_kernel/__init__.py",
            "src/academic_research_kernel/__main__.py",
            "src/academic_research_kernel/_version.py",
            "src/academic_research_kernel/cli.py",
            "src/academic_research_kernel/mcp_server.py",
            "src/academic_research_kernel/state_db.py",
        ):
            require(f"{prefix}{req_rel}" in files, f"sdist missing required asset or source module: {req_rel}")
        sdist_ver = _read_literal_version(files[f"{prefix}src/academic_research_kernel/_version.py"].decode("utf-8"))
        require(sdist_ver == version, "sdist _version.py mismatch")
        sdist_schemas = [
            k for k in files if k.startswith(f"{prefix}src/academic_research_kernel/schemas/") and k.endswith(".schema.json")
        ]
        require(len(sdist_schemas) == 26, f"sdist must include all 26 schemas, found {len(sdist_schemas)}")
        require(
            any(k.startswith(f"{prefix}src/academic_research_kernel/portable_skills/") and k.endswith("/SKILL.md") for k in files),
            "sdist missing portable SKILL.md",
        )
        if source_root is not None:
            src_pkg = source_root / "src"
            expected_src_rels = {
                "src/" + p.relative_to(src_pkg).as_posix()
                for p in src_pkg.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc")
            }
            actual_rels = set()
            for member_name, member_bytes in files.items():
                require(member_name.startswith(prefix), f"unexpected top-level sdist member: {member_name}")
                rel_s = member_name[len(prefix) :]
                if rel_s == "PKG-INFO":
                    continue
                actual_rels.add(rel_s)
                src_fp = safe_path(source_root / rel_s, root=source_root, must_exist=True)
                require(src_fp.read_bytes() == member_bytes, f"sdist member bytes differ from tagged source: {rel_s}")
            actual_src_rels = {r for r in actual_rels if r.startswith("src/")}
            require(
                actual_src_rels == expected_src_rels,
                f"sdist src/ member set differs from source tree (missing={sorted(expected_src_rels - actual_src_rels)[:5]})",
            )

    return {
        "filename": path.name,
        "sha256": sha,
        "size_bytes": len(raw_bytes),
        "file_count": len(files),
    }


def write_release_bundle(dist_dir: Path, out_dir: Path, version: str, tag: str, root: Path, *, require_main_ancestry: bool = True) -> dict[str, object]:
    target = validate_target(version, tag, root, require_head=True, require_main_ancestry=require_main_ancestry)
    expected = package_filenames(version)
    out_dir.mkdir(parents=True, exist_ok=True)
    require(not list(out_dir.iterdir()), "release bundle output directory must be empty")
    records = []
    sums_lines = []
    for fname in sorted(expected):
        src = dist_dir / fname
        info = inspect_artifact(src, version, source_root=root)
        shutil.copyfile(src, out_dir / fname)
        records.append(info)
        sums_lines.append(f"{info['sha256']}  {fname}")
    shutil.copyfile(root / "server.json", out_dir / "server.json")
    plugin = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    manifest = {
        "package": PACKAGE,
        "version": version,
        "git_tag": tag,
        "intended_tag": tag,
        "source_dirty": False,
        "source_commit": target["commit"],
        "source_tree": target["tree"],
        "tag_object": target["tag_object"],
        "plugin": {"name": plugin.get("name"), "version": plugin.get("version")},
        "artifacts": records,
    }
    (out_dir / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out_dir / "SHA256SUMS").write_text("\n".join(sums_lines) + "\n", encoding="utf-8")
    return manifest


def verify_release_directory(
    directory: Path,
    version: str,
    tag: str,
    dist: Path,
    root: Path,
    expected_commit: str | None = None,
    *,
    require_main_ancestry: bool = True,
) -> dict[str, object]:
    target = validate_target(
        version,
        tag,
        root,
        expected_commit,
        require_head=True,
        require_main_ancestry=require_main_ancestry,
    )
    expected_names = package_filenames(version)
    entries = list(directory.iterdir())
    require(all(p.is_file() and not p.is_symlink() for p in entries), "release input contains non-regular entries")
    require(
        {p.name for p in entries} == (expected_names | SIDECARS),
        "release input must contain exact wheel, sdist, release-manifest.json, SHA256SUMS, and server.json",
    )
    manifest = json.loads((directory / "release-manifest.json").read_text(encoding="utf-8"))
    require(manifest.get("package") == PACKAGE and manifest.get("version") == version, "manifest package/version mismatch")
    require(manifest.get("git_tag") == tag and manifest.get("intended_tag") == tag, "manifest tag mismatch")
    require(manifest.get("source_dirty") is False, "manifest source_dirty must be False")
    require(manifest.get("source_commit") == target["commit"], "manifest source_commit mismatch")
    require(manifest.get("source_tree") == target["tree"], "manifest source_tree mismatch")
    require(manifest.get("tag_object") == target["tag_object"], "manifest tag_object mismatch")
    require(manifest.get("plugin") == {"name": "academic-skills", "version": version}, "manifest plugin version mismatch")
    artifacts = manifest.get("artifacts")
    require(isinstance(artifacts, list) and len(artifacts) == 2, "manifest must list exactly 2 artifacts")
    require({a.get("filename") for a in artifacts if isinstance(a, dict)} == expected_names, "manifest filenames mismatch")

    verified = {}
    for art in artifacts:
        p = directory / art["filename"]
        actual = inspect_artifact(p, version, source_root=root)
        for k in ("sha256", "size_bytes", "file_count"):
            require(art.get(k) == actual[k], f"manifest {k} mismatch for {p.name}")
        verified[p.name] = actual

    sums: dict[str, str] = {}
    for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        m = re.fullmatch(r"([0-9a-f]{64}) [ *]([^/\\]+)", line)
        require(m is not None and m.group(2) not in sums, "invalid or duplicate SHA256SUMS line")
        sums[m.group(2)] = m.group(1)
    require(sums == {n: str(v["sha256"]) for n, v in verified.items()}, "SHA256SUMS differs from verified packages")

    server = json.loads((directory / "server.json").read_text(encoding="utf-8"))
    require(
        server.get("name") == "io.github.xngg1021/academic-research-kernel" and server.get("version") == version,
        "server.json name/version mismatch",
    )
    pkgs = server.get("packages")
    require(isinstance(pkgs, list) and len(pkgs) == 1, "server.json must declare 1 PyPI package")
    pkg0 = pkgs[0]
    require(
        pkg0.get("registryType") == "pypi"
        and pkg0.get("identifier") == PACKAGE
        and pkg0.get("version") == version
        and pkg0.get("transport", {}).get("type") == "stdio",
        "server.json PyPI package or stdio transport mismatch",
    )
    tagged_server = json.loads(_git(root, "show", f"{target['commit']}:server.json"))
    require(server == tagged_server, "server.json differs from tagged commit")

    require(dist.resolve() != directory.resolve(), "verified dist must differ from input directory")
    dist.mkdir(parents=True, exist_ok=True)
    require(not list(dist.iterdir()), "verified dist directory must be empty")
    for name in sorted(expected_names):
        shutil.copyfile(directory / name, dist / name)
    return manifest


def fetch_pypi_version(version: str) -> dict | None:
    validate_version_tag(version, f"v{version}")
    req = Request(
        f"https://pypi.org/pypi/{PACKAGE}/{version}/json",
        headers={"User-Agent": f"{PACKAGE}/release-gate", "Accept": "application/json"},
    )
    try:
        with controlled_urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def plan_pypi_upload(
    manifest: dict[str, object],
    verified_dist: Path,
    upload_dist: Path,
    published: dict | None,
    *,
    verify_only: bool = False,
) -> dict[str, object]:
    version = str(manifest["version"])
    validate_version_tag(version, str(manifest["git_tag"]))
    expected = {a["filename"]: a for a in manifest["artifacts"]}  # type: ignore[index]
    require(set(expected) == package_filenames(version), "upload plan filenames mismatch")
    require(verified_dist.resolve() != upload_dist.resolve(), "upload staging must differ from verified dist")
    require({p.name for p in verified_dist.iterdir()} == set(expected), "verified dist file set mismatch")
    for name, item in expected.items():
        p = verified_dist / name
        require(
            p.is_file()
            and not p.is_symlink()
            and hashlib.sha256(p.read_bytes()).hexdigest() == item["sha256"]
            and p.stat().st_size == item["size_bytes"],
            f"verified package mutated before upload planning: {name}",
        )

    remote: dict[str, dict] = {}
    if published is not None:
        info = published.get("info") or {}
        require(info.get("name") == PACKAGE and info.get("version") == version, "PyPI returned unexpected package/version")
        urls = published.get("urls")
        require(isinstance(urls, list), "PyPI urls list invalid")
        for u in urls:
            fn = u.get("filename")
            require(fn in expected and fn not in remote, f"PyPI has unexpected/duplicate file: {fn!r}")
            require(
                (u.get("digests") or {}).get("sha256") == expected[fn]["sha256"]
                and u.get("size") == expected[fn]["size_bytes"],
                f"PyPI same-version byte conflict for {fn}",
            )
            remote[fn] = u

    missing = sorted(set(expected) - set(remote))
    require((not verify_only) or (not missing), "verify-only requires both release artifacts already published on PyPI")
    upload_dist.mkdir(parents=True, exist_ok=True)
    require(not list(upload_dist.iterdir()), "upload staging directory must be empty")
    for fn in missing:
        shutil.copyfile(verified_dist / fn, upload_dist / fn)
    return {
        "version": version,
        "already_published": sorted(remote),
        "missing": missing,
        "upload_count": len(missing),
    }


def _scrubbed_env() -> dict[str, str]:
    env = dict(os.environ)
    for k in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(k, None)
    return env


def run_command_smoke(cmd_prefix: list[str], expected_version: str) -> dict[str, object]:
    require(bool(cmd_prefix), "smoke command prefix cannot be empty")
    env = _scrubbed_env()
    with tempfile.TemporaryDirectory() as td:
        cwd = Path(td)
        v_out = subprocess.check_output([*cmd_prefix, "--version"], cwd=cwd, env=env, text=True, encoding="utf-8").strip()
        require(expected_version in v_out, f"--version output {v_out!r} did not match {expected_version!r}")

        doc_out = subprocess.check_output([*cmd_prefix, "doctor", "--json"], cwd=cwd, env=env, text=True, encoding="utf-8")
        doc = json.loads(doc_out)
        require(doc.get("status") == "ok" and doc.get("version") == expected_version, f"doctor failed: {doc}")
        require(doc.get("schema_resources", {}).get("count") == 26, "doctor schema count != 26")

        skill_dir = cwd / "exported-skill"
        sk_out = subprocess.check_output(
            [*cmd_prefix, "research", "skill", "--output", str(skill_dir)],
            cwd=cwd,
            env=env,
            text=True,
            encoding="utf-8",
        )
        sk = json.loads(sk_out)
        require((skill_dir / "SKILL.md").is_file() and sk.get("version") == expected_version, "skill export smoke failed")

        # Real JSON-RPC 2.0 round-trip over stdio MCP
        rpc_reqs = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "release-gate", "version": "1.0"}}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "academic_check_percentage", "arguments": {"count": 8, "percent": 25.0, "n": 32}}}),
        ]) + "\n"
        mcp_proc = subprocess.run(
            [*cmd_prefix, "mcp"],
            input=rpc_reqs,
            cwd=cwd,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
            check=True,
        )
        lines = [json.loads(ln) for ln in mcp_proc.stdout.splitlines() if ln.strip()]
        require(len(lines) == 3, f"expected 3 JSON-RPC responses, got {len(lines)}")
        tools = lines[1]["result"]["tools"]
        require(len(tools) == 24, f"expected 24 MCP tools, got {len(tools)}")
        call_res = json.loads(lines[2]["result"]["content"][0]["text"])
        require(call_res.get("consistent") is True, f"MCP tool call check failed: {call_res}")
    return {"status": "ok", "version": expected_version, "mcp_tools": 24}


def _venv_console_script(venv_dir: Path) -> Path:
    if os.name == "nt":
        for cand in ("Scripts/academic-research-kernel.exe", "Scripts/academic-research-kernel.cmd", "Scripts/academic-research-kernel"):
            p = venv_dir / cand
            if p.is_file():
                return p
        return venv_dir / "Scripts/academic-research-kernel.exe"
    return venv_dir / "bin/academic-research-kernel"


def _build_wheel_from_sdist(sdist_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    uv_bin = shutil.which("uv")
    if uv_bin:
        r = subprocess.run(
            [uv_bin, "build", "--wheel", "--no-create-gitignore", "--out-dir", str(out_dir), str(sdist_path)],
            env=_scrubbed_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        built = sorted(out_dir.glob("*.whl"))
        if r.returncode == 0 and len(built) == 1:
            return built[0]
    # Fallback: use current interpreter's pip wheel --no-deps (--no-build-isolation first when hatchling is present)
    for extra_flags in (["--no-deps", "--no-build-isolation"], ["--no-deps"]):
        for old_w in out_dir.glob("*.whl"):
            old_w.unlink()
        r_pip = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--quiet", "--disable-pip-version-check", *extra_flags, str(sdist_path), "--wheel-dir", str(out_dir)],
            env=_scrubbed_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        built = sorted(out_dir.glob("*.whl"))
        if r_pip.returncode == 0 and len(built) == 1:
            return built[0]
    raise ValueError(f"Failed to build wheel from sdist {sdist_path}")


def run_package_acceptance(dist_dir: Path, *, source_root: Path | None = None) -> dict[str, object]:
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    require(len(wheels) == 1 and len(sdists) == 1, f"dist directory {dist_dir} must contain exactly 1 wheel and 1 sdist")
    m = re.match(rf"^{DIST_PREFIX}-(\d+\.\d+\.\d+)-py3-none-any\.whl$", wheels[0].name)
    require(m is not None, f"cannot parse version from wheel {wheels[0].name}")
    version = m.group(1)
    eff_root = source_root
    if eff_root is None and (Path.cwd() / "pyproject.toml").is_file() and (Path.cwd() / "src" / "academic_research_kernel").is_dir():
        eff_root = Path.cwd()
    inspect_artifact(wheels[0], version, source_root=eff_root)
    inspect_artifact(sdists[0], version, source_root=eff_root)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # 1. Isolated venv A: install published wheel and verify BOTH console script AND python -m
        venv_whl = tmp / "isolated-venv-wheel"
        venv.EnvBuilder(with_pip=True).create(venv_whl)
        py_whl = venv_whl / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [str(py_whl), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", str(wheels[0])],
            env=_scrubbed_env(),
            check=True,
        )
        cli_whl = _venv_console_script(venv_whl)
        require(cli_whl.is_file(), f"installed wheel did not create console script {cli_whl}")
        res_whl = run_command_smoke([str(cli_whl)], version)
        run_command_smoke([str(py_whl), "-I", "-m", "academic_research_kernel"], version)

        # 2. Isolated venv B: build wheel from published sdist, inspect it, install it, and verify console script
        sdist_whl = _build_wheel_from_sdist(sdists[0], tmp / "sdist-built-wheel")
        inspect_artifact(sdist_whl, version, source_root=eff_root)
        venv_sd = tmp / "isolated-venv-sdist"
        venv.EnvBuilder(with_pip=True).create(venv_sd)
        py_sd = venv_sd / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [str(py_sd), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", str(sdist_whl)],
            env=_scrubbed_env(),
            check=True,
        )
        cli_sd = _venv_console_script(venv_sd)
        require(cli_sd.is_file(), f"sdist-built wheel did not create console script {cli_sd}")
        run_command_smoke([str(cli_sd)], version)
        return res_whl


def _write_github_outputs(path: Path | None, values: dict[str, object]) -> None:
    if path is not None:
        with path.open("a", encoding="utf-8") as fh:
            for k, v in values.items():
                fh.write(f"{k}={v}\n")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    # Split '--' passthrough command for --distribution-smoke
    smoke_cmd: list[str] = []
    if "--" in argv:
        sep = argv.index("--")
        smoke_cmd = argv[sep + 1 :]
        argv = argv[:sep]

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", nargs="?", type=Path)
    ap.add_argument("--version")
    ap.add_argument("--tag")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--expected-commit")
    ap.add_argument("--validate-target", action="store_true")
    ap.add_argument("--allow-branch", action="store_true", help="skip origin/main ancestry check during local branch dry-runs")
    ap.add_argument("--write-bundle", type=Path, help="write release-manifest.json, SHA256SUMS, server.json, and packages to dir")
    ap.add_argument("--dist", type=Path, default=Path("dist"))
    ap.add_argument("--pypi-upload-dir", type=Path)
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--package-acceptance", action="store_true")
    ap.add_argument("--distribution-smoke", action="store_true")
    ap.add_argument("--expected-version")
    ap.add_argument("--github-output", type=Path)
    args = ap.parse_args(argv)

    if args.package_acceptance:
        res = run_package_acceptance(args.dist)
        print(json.dumps(res))
        return 0

    if args.distribution_smoke:
        require(bool(args.expected_version), "--distribution-smoke requires --expected-version")
        cmd = smoke_cmd if smoke_cmd else [sys.executable, "-I", "-m", "academic_research_kernel"]
        res = run_command_smoke(cmd, args.expected_version)
        print(json.dumps(res))
        return 0

    require(bool(args.version and args.tag), "--version and --tag are required")
    req_main = not bool(args.allow_branch)

    if args.validate_target:
        target = validate_target(args.version, args.tag, args.repo, args.expected_commit, require_main_ancestry=req_main)
        _write_github_outputs(args.github_output, target)
        print(json.dumps(target))
        return 0

    if args.write_bundle is not None:
        manifest = write_release_bundle(args.dist, args.write_bundle, args.version, args.tag, args.repo, require_main_ancestry=req_main)
        print(json.dumps(manifest))
        return 0

    require(args.directory is not None, "release input directory is required")
    manifest = verify_release_directory(
        args.directory,
        args.version,
        args.tag,
        args.dist,
        args.repo,
        args.expected_commit,
        require_main_ancestry=req_main,
    )
    if args.pypi_upload_dir is not None:
        published = fetch_pypi_version(args.version)
        plan = plan_pypi_upload(manifest, args.dist, args.pypi_upload_dir, published, verify_only=args.verify_only)
        _write_github_outputs(args.github_output, {"upload_count": plan["upload_count"]})
        print(json.dumps(plan))
    else:
        print(json.dumps({"status": "verified", "version": args.version}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
