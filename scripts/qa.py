"""Offline QA. Executes only classified smoke fences, always in fresh subprocesses."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r'^```python\s*\n(.*?)^```\s*$', re.M | re.S)
KINDS = ('smoke-test: true', 'external-test: true', 'fragment:')


EXCLUDED_TREES = {'.git', '.venv', 'venv', 'env', '.pytest_cache', '.mypy_cache',
                  '.ruff_cache', '.tox', '.nox', 'build', 'dist', '__pycache__',
                  'node_modules', 'htmlcov', '.cache', '.uv-cache', '.coverage',
                  '.hermes-upstream', '.hermes-latest', '.local-lineage'}
SOURCE_ROOTS = {'scripts', 'src', 'skills', 'schemas', 'docs', 'tests', 'i18n',
                'LICENSES', '.github', 'tools'}


def source_files(root=ROOT):
    """Tracked files in Git; explicit roots in source archives. Never follow links."""
    root = root.resolve()
    if (root / '.git').exists():
        result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'],
                                capture_output=True, check=True)
        candidates = [root / os.fsdecode(p) for p in result.stdout.split(b'\0') if p]
    else:
        candidates = []
        for directory, dirs, files in os.walk(root, followlinks=False):
            base = Path(directory)
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_TREES
                             and not (base / d).is_symlink()
                             and (base != root or d in SOURCE_ROOTS))
            candidates.extend(base / name for name in files)
    return sorted(p for p in candidates if p.is_file()
                  and not any(part in EXCLUDED_TREES for part in p.relative_to(root).parts)
                  and not any(parent.is_symlink() for parent in [p, *p.parents] if parent != root)
                  and p.resolve().is_relative_to(root))


def fences(path):
    text = path.read_text(encoding='utf-8')
    for i, match in enumerate(FENCE.finditer(text), 1):
        code = match.group(1)
        kinds = [kind for kind in KINDS if any(line.strip().startswith('# ' + kind) for line in code.splitlines())]
        if len(kinds) != 1:
            raise ValueError(f'{path}:{i}: exactly one fence classification required')
        yield i, kinds[0], code


def code_issues(code):
    tree = ast.parse(code)
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {'savefig', 'open'} and node.args:
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) and node.args[0].value.startswith('~/'):
                    errors.append('unexpanded tilde passed to file API')
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            names = []
            for side in [node.left, node.right]:
                if isinstance(side, ast.Call) and isinstance(side.func, ast.Attribute):
                    names.append(side.func.attr)
            if set(names) == {'read_csv', 'read_excel'}:
                errors.append('CSV/Excel pseudo-alternative is DataFrame division')
    return errors


BANNED_TOKEN_SHA256 = frozenset([
    "0d3875158b04bb14f5cd67a2ba54f480848ca94aec7a4aa2ca94c712c04be55f",
    "11987c60f4c83ac9199d79c59b32f37ec5dc07443f1f881353e79ca643bcea57",
    "30522def353fdb96b4270ed4e44e5f925f7cedec9651ebd8c0e21ba319e2ede9",
    "309c81d675e41940438bee673bd5b877c55aee03a37a7a7e9ff9dda674d254ad",
    "3f178fe43b688a406a252fc7b8b25d7670ad939509905159d741ee5185d73310",
    "468764310f068a00fdfa43d3a202b86a2e529079129d86e51c3620dc287c3422",
    "5c1b70d8678fde4217414c5ac78c614e088814d091db8e7eea9741fd4b351291",
    "6c277575446c91c1d49465940d84d128f43394a06b5ef8c775b5aca4fcdbae31",
    "73a5ebb82c02c74260d707847837d3a19478844ac0608e976f1c1e1de038283a",
    "7a9c5cfe8aa8f9c564bc7c0ea50f8267a16f38a93733d6fbd9a1771140979cd0",
    "8ef4091ea30686929943b7734250a9d0e84c0e80fffe385f76b54ad88c9f5ac2",
    "9d681ad61b95d6653bf1011354205d4c299f5874f6003814eb852939bf5d687a",
    "aad8b6c3c3c9b33614bab058d0378eac1da1202a138f729c6e450d9ffe3073c8",
    "abf49cd072079260ad3b499c3fc7b4914134aa2b6c75c3ae40e7428b912e7554",
    "b3d54f72aca745dc2ddea3c899d33ce904fe759bf747c8a671b4d4d0034a2391",
    "c83bf41fd8fc032e42e75002b1b994956545f3d9ecd72db8d7df79dff4d8e327",
    "c9a7b24a282314d9fc9337a33ad61714135a639d985054efea2d7c1bf84a2e83",
    "cae755a665553d96911396d77e1a5151d39f57f7aefde27ca6f6cb25b77430c3",
    "d55851b489264fc2a373cb1d5de4fa965a900dcf62f476c3b4cceb00130109df",
    "d69db26afa12005be9202f63499ebec6a2b79afa541ce0b1f3c5dc6384a1b8cc",
    "da2b491830473d09a13bbaa262e6a01c6248d96c0f2f1b942d54e0aab3f7a1a9",
    "ed08e61f3aae536101a0b0290098ec338d9ee1c4e876f0874cac95761366ac1f",
    "ee605c8c3cb751639c13a6a5b498643bc38fa55d255f82c1e9f1b4c8bf5e2777",
    "f2753a428cd96b8db17d368c803bb913d9bd5212b17831b60538a4209afd29b2",
    "f962119a8d8b377c9a74b608244ce367b77dbae9ee69b8cbcab17ccdf9b5cda8",
    "fd0a5e8c07b3d055c602ffc46a712e5620a18da3f9871860ef9f6a9d267fd9aa"
])


def hygiene(text):
    patterns = [r'(?i)\b[A-Z]:[\\/]+Users[\\/]+(?!<)[\w.-]+',
                r'(?i)\b[A-Z]:[\\/]+[a-z]+-home\b',
                r'/(?:Users|home)/(?!<|runner\b)[\w.-]+/',
                r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{24,})\b',
                r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                r'''(?i)(?:^|(?<=[^A-Za-z0-9]))(?:api_key|access_token|secret|password)\s*[:=]\s*["'](?!<|YOUR_|example|placeholder|test)[A-Za-z0-9_-]{16,}["']''']
    hits = ['<redacted-pattern-hit>' for pat in patterns for _ in re.finditer(pat, text)]
    candidates = set(re.findall(r'[A-Za-z0-9_.-]{4,}', text))
    candidates.update(re.findall(r'[A-Za-z0-9_]{4,}', text))
    for run in re.findall(r'[\u4e00-\u9fff]{2,}', text):
        for wlen in (2, 3, 4):
            for idx in range(len(run) - wlen + 1):
                candidates.add(run[idx:idx + wlen])
    for tok in candidates:
        if hashlib.sha256(tok.lower().encode('utf-8')).hexdigest() in BANNED_TOKEN_SHA256:
            hits.append('<redacted-token-hash-hit>')
    return hits


def reference_issues(path, root=ROOT):
    text = path.read_text(encoding='utf-8')
    candidates = re.findall(r'\[[^\]]*\]\(([^)]+)\)', text)
    candidates += re.findall(r'`((?:references|scripts)/[^`\s]+\.\w+)`', text)
    errors = []
    for target in candidates:
        target = target.split('#', 1)[0]
        if not target or '://' in target or target.startswith('mailto:'):
            continue
        if any(c in target for c in '<>*'):
            continue  # explicit template / glob, not a concrete reference
        dest = path.parent / target
        if not dest.exists():
            errors.append(f'missing or case-mismatched reference: {target}')
        elif not dest.resolve().is_relative_to(root.resolve()):
            errors.append(f'reference outside repository: {target}')
        else:
            actual = path.parent
            for part in Path(target).parts:
                if part == '..':
                    actual = actual.parent
                elif part != '.':
                    if part not in {entry.name for entry in actual.iterdir()}:
                        errors.append(f'case mismatch: {target}')
                        break
                    actual = actual / part
    return errors


def static_checks(root=ROOT):
    import yaml
    errors, names = [], set()
    inventory = source_files(root)
    readme = (root / 'README.md').read_text(encoding='utf-8')
    paths = [p for p in inventory if p.name == 'SKILL.md' and len(p.relative_to(root).parts) == 3 and p.relative_to(root).parts[0] == 'skills']
    nested = [p for p in inventory if p.name == 'SKILL.md' and p.relative_to(root).parts[0] == 'skills']
    if not paths:
        errors.append('no skills found directly under skills/')
    if len(nested) != len(paths):
        errors.append('skills must live directly under skills/, no nested skill directories')
    for path in paths:
        text = path.read_text(encoding='utf-8')
        try:
            assert text.startswith('---\n')
            fm = yaml.safe_load(text.split('---', 2)[1])
            assert isinstance(fm, dict)
            for key in ('name', 'description', 'version', 'author', 'license', 'platforms'):
                assert key in fm, f'missing {key}'
            name = fm['name']
            assert name == path.parent.name and re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', name)
            assert name not in names, f'duplicate name {name}'
            names.add(name)
            assert isinstance(fm['version'], str) and re.fullmatch(r'\d+\.\d+\.\d+', fm['version'])
            assert isinstance(fm['description'], str) and 0 < len(fm['description']) <= 60
            assert fm['description'].endswith('.')
            assert isinstance(fm['platforms'], list) and set(fm['platforms']) <= {'linux', 'macos', 'windows'} and fm['platforms']
            tags = fm.get('tags') or (fm.get('metadata', {}).get('hermes', {}).get('tags') if isinstance(fm.get('metadata'), dict) else None)
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',') if t.strip()]
            assert isinstance(tags, list) and tags and all(isinstance(t, str) and t for t in tags), 'tags missing or invalid'
            rel = fm.get('related_skills') or (fm.get('metadata', {}).get('hermes', {}).get('related_skills', []) if isinstance(fm.get('metadata'), dict) else [])
            if isinstance(rel, str):
                rel = [r.strip() for r in rel.split(',') if r.strip()]
            assert isinstance(rel, list), 'related_skills invalid'
            assert f'| `skills/{name}` | {fm["version"]} |' in readme, 'README version mismatch'
            section = text.split('## Verification', 1)[1]
            assert re.search(r'# (?:smoke|external)-test: true', section), 'Verification not executable'
        except (AssertionError, KeyError, IndexError, TypeError, yaml.YAMLError) as e:
            errors.append(f'{path.relative_to(root)}: frontmatter/verification {e}')
    for path in (p for p in inventory if p.suffix == '.md'):
        if '.git' in path.parts or '.pytest_cache' in path.parts:
            continue
        errors.extend(f'{path.relative_to(root)}: {e}' for e in reference_issues(path, root))
        try:
            for i, kind, code in fences(path):
                errors.extend(f'{path.relative_to(root)}:{i}: {e}' for e in code_issues(code))
        except (ValueError, SyntaxError) as e:
            errors.append(str(e))

    # Load i18n manifest metadata for document classifications
    doc_meta_by_path = {}
    manifest_path = root / "docs" / "i18n" / "manifest.json"
    manifest = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for doc_entry in manifest.get("documents", []):
                doc_meta_by_path[doc_entry["source_path"]] = {
                    "genre": doc_entry.get("genre", "user_facing_documentation"),
                    "intensity": doc_entry.get("style_intensity", "strong"),
                    "locale": doc_entry.get("source_locale", "en"),
                }
                for loc, inst in doc_entry.get("localized_instances", {}).items():
                    doc_meta_by_path[inst["path"]] = {
                        "genre": doc_entry.get("genre", "user_facing_documentation"),
                        "intensity": doc_entry.get("style_intensity", "strong"),
                        "locale": loc,
                    }
        except Exception as e:
            errors.append(f"i18n manifest load failed: {e}")

    # Load all 21 locale profiles
    profiles_dir = root / "docs" / "style" / "profiles"
    locale_profiles = {}
    if profiles_dir.is_dir():
        for prof_file in sorted(profiles_dir.glob("*.json")):
            try:
                locale_profiles[prof_file.stem] = json.loads(prof_file.read_text(encoding="utf-8"))
            except Exception as e:
                errors.append(f"failed loading profile {prof_file.name}: {e}")

    EXPECTED_LOCALES = {
        "en", "zh-Hans", "zh-Hant", "es", "pt", "fr", "de", "ru", "ja", "ko",
        "id", "it", "hi", "ar", "bn", "ur", "vi", "tr", "fa", "sw", "pl"
    }
    if set(locale_profiles.keys()) != EXPECTED_LOCALES:
        errors.append(f"Style profile invariant failed: expected exactly 21 profiles {sorted(EXPECTED_LOCALES)}, got {sorted(locale_profiles.keys())}")
    for loc_code, prof_data in locale_profiles.items():
        for rule_grp in ("banned_phrases", "step_broadcasting_markers", "redundant_hedges"):
            items = prof_data.get(rule_grp)
            if not isinstance(items, list) or len(items) == 0:
                errors.append(f"Profile '{loc_code}' invariant failed: rule group '{rule_grp}' must be a non-empty list")

    # Legacy Chinese aliases byte-parity gate
    zh_cn = root / "README.zh-CN.md"
    zh_hans = root / "README.zh-Hans.md"
    zh_tw = root / "README.zh-TW.md"
    zh_hant = root / "README.zh-Hant.md"
    if zh_cn.is_file() and zh_hans.is_file():
        if zh_cn.read_bytes() != zh_hans.read_bytes():
            errors.append("Legacy alias parity failed: README.zh-CN.md is not byte-identical to README.zh-Hans.md")
    if zh_tw.is_file() and zh_hant.is_file():
        if zh_tw.read_bytes() != zh_hant.read_bytes():
            errors.append("Legacy alias parity failed: README.zh-TW.md is not byte-identical to README.zh-Hant.md")

    # 1. Terminology registry gate
    term_reg_path = root / "docs" / "terminology" / "registry.json"
    if term_reg_path.is_file():
        try:
            term_reg = json.loads(term_reg_path.read_text(encoding="utf-8"))
            concepts = term_reg.get("concepts", {})
            if len(concepts) != 18:
                errors.append(f"Terminology registry invariant failed: expected 18 concepts, got {len(concepts)}")
            for c_id, c_info in concepts.items():
                labels = c_info.get("preferred_label", {})
                if set(labels.keys()) != EXPECTED_LOCALES:
                    errors.append(f"Terminology registry invariant failed for concept '{c_id}': missing locales {sorted(EXPECTED_LOCALES - set(labels.keys()))}")
            banned_jargon = set()
            for c_info in concepts.values():
                if c_info.get("forbidden_in_user_docs"):
                    for loc_list in c_info.get("deprecated_labels", {}).values():
                        banned_jargon.update(loc_list)
            banned_jargon.update([
                "レジャー", "영수증", "Beschneidungskausalität", "causalité d’élagage",
                "causalidad de poda", "台账内核", "Truth Authority", "State Ledger本体"
            ])
            for doc_path in (p for p in inventory if p.suffix == ".md"):
                if '.git' in doc_path.parts or '.pytest_cache' in doc_path.parts:
                    continue
                rel_str = "/".join(doc_path.relative_to(root).parts)
                meta = doc_meta_by_path.get(rel_str)
                intensity = meta["intensity"] if meta else ("audit_safe" if any(k in rel_str for k in ["CHANGELOG", "LICENSE", "SOURCE-LINEAGE", "audit"]) else "strong")
                if intensity != "strong" or "docs/terminology" in rel_str:
                    continue
                doc_text = doc_path.read_text(encoding="utf-8")
                for term in banned_jargon:
                    if term in doc_text:
                        errors.append(f"{rel_str}: user-facing doc contains banned jargon: '{term}'")
        except Exception as e:
            errors.append(f"terminology registry QA check failed: {e}")

    # 2. Style style contract and per-locale profiles gate
    style_contract_path = root / "docs" / "style" / "style-contract.json"
    if style_contract_path.is_file():
        try:
            style_contract = json.loads(style_contract_path.read_text(encoding="utf-8"))
            prohibited_patterns = style_contract.get("prohibited_patterns", {})
            for doc_path in (p for p in inventory if p.suffix == ".md"):
                if '.git' in doc_path.parts or '.pytest_cache' in doc_path.parts:
                    continue
                rel_str = "/".join(doc_path.relative_to(root).parts)
                meta = doc_meta_by_path.get(rel_str)
                intensity = meta["intensity"] if meta else ("audit_safe" if any(k in rel_str for k in ["CHANGELOG", "LICENSE", "SOURCE-LINEAGE", "audit"]) else "strong")
                loc = meta["locale"] if meta else "en"

                if intensity == "audit_safe" or any(ex in rel_str for ex in ["style-contract", "docs/terminology", "docs/standards"]):
                    continue

                doc_text = doc_path.read_text(encoding="utf-8")

                # Universal Chinese prohibited patterns for Chinese documentation
                if loc in ("zh-Hans", "zh-Hant") or any(ord(c) > 127 for c in rel_str):
                    for pat in prohibited_patterns.get("synthetic_hyperbole", []) + prohibited_patterns.get("jargon_stacking", []):
                        if pat in doc_text:
                            errors.append(f"{rel_str}: Style prohibited pattern detected: '{pat}'")
                    if intensity == "strong":
                        for pat in prohibited_patterns.get("step_broadcasting", []):
                            if pat in doc_text:
                                errors.append(f"{rel_str}: Style step broadcasting detected: '{pat}'")

                # Dedicated per-locale profile check for user-facing documentation
                if intensity == "strong" and loc in locale_profiles:
                    prof = locale_profiles[loc]
                    for phrase in prof.get("banned_phrases", []):
                        if phrase.lower() in doc_text.lower():
                            errors.append(f"{rel_str}: [{loc}] banned phrase detected: '{phrase}'")
                    for marker in prof.get("step_broadcasting_markers", []):
                        if marker.lower() in doc_text.lower():
                            errors.append(f"{rel_str}: [{loc}] step broadcasting detected: '{marker}'")
                    for hedge in prof.get("redundant_hedges", []):
                        if hedge.lower() in doc_text.lower():
                            errors.append(f"{rel_str}: [{loc}] redundant hedge detected: '{hedge}'")
        except Exception as e:
            errors.append(f"Style contract QA check failed: {e}")

    # 3. Multilingual synchronization manifest integrity gate
    if manifest:
        try:
            canonical_docs = manifest.get("documents", [])
            if len(canonical_docs) != 50:
                errors.append(f"i18n manifest incomplete: expected 50 canonical documents, got {len(canonical_docs)}")
            if manifest.get("total_theoretical_instances") != 1050:
                errors.append(f"i18n manifest invariant failed: expected 1050 theoretical instances, got {manifest.get('total_theoretical_instances')}")
            recomputed_counts = {
                "canonical_current": 0,
                "localized_current": 0,
                "localized_stale": 0,
                "queued_for_generation": 0,
            }
            for doc_entry in canonical_docs:
                instances = doc_entry.get("localized_instances", {})
                if set(instances.keys()) != EXPECTED_LOCALES:
                    errors.append(f"i18n manifest instance parity failed for {doc_entry['source_path']}: expected 21 locales, got {sorted(instances.keys())}")
                for inst_data in instances.values():
                    st_val = inst_data.get("status")
                    recomputed_counts[st_val] = recomputed_counts.get(st_val, 0) + 1
            if manifest.get("status_summary") != recomputed_counts:
                errors.append(f"i18n manifest status_summary mismatch: declared {manifest.get('status_summary')}, recomputed {recomputed_counts}")
            for doc_entry in canonical_docs:
                src_file = root / doc_entry["source_path"]
                if not src_file.is_file():
                    errors.append(f"i18n manifest source file missing: {doc_entry['source_path']}")
                    continue
                content_sha = hashlib.sha256(src_file.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
                if content_sha != doc_entry.get("source_sha256"):
                    errors.append(f"i18n manifest source SHA mismatch for {doc_entry['source_path']} (run scripts/i18n_sync.py to refresh)")

                for loc, inst in doc_entry.get("localized_instances", {}).items():
                    st = inst.get("status")
                    if st in ("localized_current", "localized_stale"):
                        loc_file = root / inst["path"]
                        if not loc_file.is_file():
                            errors.append(f"Missing physical localized file for {inst['path']}")
                            continue
                        cur_loc_sha = hashlib.sha256(loc_file.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
                        if cur_loc_sha != inst.get("localized_file_sha256"):
                            errors.append(f"SHA mismatch for localized file {inst['path']} (run scripts/i18n_sync.py to refresh)")
                        if st == "localized_current" and inst.get("translated_from_source_sha256") != doc_entry["source_sha256"]:
                            errors.append(f"Falsely marked localized_current for stale source: {inst['path']}")
                        if st == "localized_stale" and inst.get("translated_from_source_sha256") == doc_entry["source_sha256"]:
                            errors.append(f"Falsely marked localized_stale for synchronized source: {inst['path']}")
        except Exception as e:
            errors.append(f"i18n manifest QA check failed: {e}")

    for path in inventory:
        if not path.is_file() or '.git' in path.parts or '__pycache__' in path.parts or '.pytest_cache' in path.parts:
            continue
        if path.suffix not in {'.md', '.py', '.json', '.yaml', '.yml', '.txt'}:
            continue
        errors.extend(f'{path.relative_to(root)}: personal path or secret detected' for _ in hygiene(path.read_text(encoding='utf-8')))
    return errors


def run_fence(path, index, code, timeout=120, mpl_dir=None):
    with tempfile.TemporaryDirectory(prefix='hermes-qa-') as temp:
        script = Path(temp) / 'example.py'
        script.write_text(code, encoding='utf-8')
        skill = next(p for p in [path.parent, *path.parents] if (p / 'SKILL.md').exists())
        base_env = {k: v for k, v in os.environ.items() if k not in ('PYTHONOPTIMIZE', 'PYTHONPATH', 'PYTHONHOME')}
        env = dict(base_env, MPLBACKEND='Agg', MPLCONFIGDIR=str(mpl_dir or (Path(temp) / 'mpl')),
                   SKILL_DIR=str(skill), PLOT_DIR=str(Path(temp) / 'plots'), PYTHONIOENCODING='utf-8', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        return subprocess.run([sys.executable, str(script)], cwd=skill, env=env,
                              capture_output=True, text=True, encoding='utf-8', timeout=timeout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--static-only', action='store_true')
    args = parser.parse_args()
    errors = static_checks()
    count = 0
    if not args.static_only:
        with tempfile.TemporaryDirectory(prefix='hermes-qa-mpl-') as shared_mpl:
            for path in (p for p in source_files(ROOT) if p.suffix == '.md' and p.relative_to(ROOT).parts[0] == 'skills'):
                for i, kind, code in fences(path):
                    if kind != 'smoke-test: true':
                        continue
                    count += 1
                    try:
                        result = run_fence(path, i, code, mpl_dir=shared_mpl)
                        if result.returncode:
                            errors.append(f'{path.relative_to(ROOT)}:{i}: {result.stderr}')
                    except subprocess.TimeoutExpired:
                        errors.append(f'{path.relative_to(ROOT)}:{i}: timeout')
    if errors:
        print('\n'.join(errors))
        return 1
    print(f'PASS static QA; {count} independent executable fences')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
