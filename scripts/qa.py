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

import yaml

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r'^```python\s*\n(.*?)^```\s*$', re.M | re.S)
KINDS = ('smoke-test: true', 'external-test: true', 'fragment:')


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


def hygiene(text):
    patterns = [r'(?i)\b[A-Z]:[/\\]+Users[/\\]+(?!<)[\w.-]+',
                r'/(?:Users|home)/(?!<|runner\b)[\w.-]+/',
                r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{24,})\b',
                r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                r'''(?i)\b(?:api_key|access_token|secret|password)\s*[:=]\s*["'](?!<|YOUR_|example|placeholder|test)[A-Za-z0-9_-]{16,}["']''']
    return [m.group() for pat in patterns for m in re.finditer(pat, text)]


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
    errors, names = [], set()
    readme = (root / 'README.md').read_text(encoding='utf-8')
    paths = sorted(root.glob('skills/*/SKILL.md'))
    nested = list(root.glob('skills/**/SKILL.md'))
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
    for path in sorted(root.rglob('*.md')):
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
                    "intensity": doc_entry.get("aidetox_intensity", "strong"),
                    "locale": doc_entry.get("source_locale", "en"),
                }
                for loc, inst in doc_entry.get("localized_instances", {}).items():
                    doc_meta_by_path[inst["path"]] = {
                        "genre": doc_entry.get("genre", "user_facing_documentation"),
                        "intensity": doc_entry.get("aidetox_intensity", "strong"),
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
        errors.append(f"AIDetox profile invariant failed: expected exactly 21 profiles {sorted(EXPECTED_LOCALES)}, got {sorted(locale_profiles.keys())}")

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
            for doc_path in root.rglob("*.md"):
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

    # 2. AIDetox style contract and per-locale profiles gate
    aidetox_path = root / "docs" / "style" / "aidetox-contract.json"
    if aidetox_path.is_file():
        try:
            aidetox_contract = json.loads(aidetox_path.read_text(encoding="utf-8"))
            prohibited_patterns = aidetox_contract.get("prohibited_patterns", {})
            for doc_path in root.rglob("*.md"):
                if '.git' in doc_path.parts or '.pytest_cache' in doc_path.parts:
                    continue
                rel_str = "/".join(doc_path.relative_to(root).parts)
                meta = doc_meta_by_path.get(rel_str)
                intensity = meta["intensity"] if meta else ("audit_safe" if any(k in rel_str for k in ["CHANGELOG", "LICENSE", "SOURCE-LINEAGE", "audit"]) else "strong")
                loc = meta["locale"] if meta else "en"

                if intensity == "audit_safe" or any(ex in rel_str for ex in ["aidetox-contract", "docs/terminology", "docs/standards"]):
                    continue

                doc_text = doc_path.read_text(encoding="utf-8")

                # Universal Chinese prohibited patterns for Chinese documentation
                if loc in ("zh-Hans", "zh-Hant") or any(ord(c) > 127 for c in rel_str):
                    for pat in prohibited_patterns.get("synthetic_hyperbole", []) + prohibited_patterns.get("jargon_stacking", []):
                        if pat in doc_text:
                            errors.append(f"{rel_str}: AIDetox prohibited pattern detected: '{pat}'")
                    if intensity == "strong":
                        for pat in prohibited_patterns.get("step_broadcasting", []):
                            if pat in doc_text:
                                errors.append(f"{rel_str}: AIDetox step broadcasting detected: '{pat}'")

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
            errors.append(f"AIDetox contract QA check failed: {e}")

    # 3. Multilingual synchronization manifest integrity gate
    if manifest:
        try:
            canonical_docs = manifest.get("documents", [])
            if len(canonical_docs) != 53:
                errors.append(f"i18n manifest incomplete: expected 53 canonical documents, got {len(canonical_docs)}")
            if manifest.get("total_theoretical_instances") != 1113:
                errors.append(f"i18n manifest invariant failed: expected 1113 theoretical instances, got {manifest.get('total_theoretical_instances')}")
            for doc_entry in canonical_docs:
                instances = doc_entry.get("localized_instances", {})
                if set(instances.keys()) != EXPECTED_LOCALES:
                    errors.append(f"i18n manifest instance parity failed for {doc_entry['source_path']}: expected 21 locales, got {sorted(instances.keys())}")
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

    for path in root.rglob('*'):
        if not path.is_file() or '.git' in path.parts or '__pycache__' in path.parts or '.pytest_cache' in path.parts:
            continue
        if path.suffix not in {'.md', '.py', '.json', '.yaml', '.yml', '.txt'}:
            continue
        errors.extend(f'{path.relative_to(root)}: personal path or secret detected' for _ in hygiene(path.read_text(encoding='utf-8')))
    return errors


def run_fence(path, index, code, timeout=120):
    with tempfile.TemporaryDirectory(prefix='hermes-qa-') as temp:
        script = Path(temp) / 'example.py'
        script.write_text(code, encoding='utf-8')
        skill = next(p for p in [path.parent, *path.parents] if (p / 'SKILL.md').exists())
        env = dict(os.environ, MPLBACKEND='Agg', MPLCONFIGDIR=str(Path(temp) / 'mpl'),
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
        for path in sorted((ROOT / 'skills').rglob('*.md')):
            for i, kind, code in fences(path):
                if kind != 'smoke-test: true':
                    continue
                count += 1
                try:
                    result = run_fence(path, i, code)
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
