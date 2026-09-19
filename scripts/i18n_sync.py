#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic Multilingual Documentation Synchronization Engine.

Computes whole-file and section-level cryptographic hashes (SHA-256) for all
53 canonical logical markdown documents, tracks parity across 21 target locales,
and verifies synchronization status against docs/i18n/manifest.json with
explicit section-level staleness detection.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "i18n" / "manifest.json"
TERMINOLOGY_PATH = ROOT / "docs" / "terminology" / "registry.json"
AIDETOX_PATH = ROOT / "docs" / "style" / "aidetox-contract.json"

TARGET_LOCALES = [
    {"code": "en", "name": "English", "tier": "global_core"},
    {"code": "zh-Hans", "name": "Simplified Chinese", "tier": "global_core", "legacy_alias": "zh-CN"},
    {"code": "zh-Hant", "name": "Traditional Chinese", "tier": "global_core", "legacy_alias": "zh-TW"},
    {"code": "es", "name": "Spanish", "tier": "global_core"},
    {"code": "pt", "name": "Portuguese", "tier": "global_core"},
    {"code": "fr", "name": "French", "tier": "global_core"},
    {"code": "de", "name": "German", "tier": "global_core"},
    {"code": "ru", "name": "Russian", "tier": "global_core"},
    {"code": "ja", "name": "Japanese", "tier": "global_core"},
    {"code": "ko", "name": "Korean", "tier": "global_core"},
    {"code": "id", "name": "Indonesian", "tier": "global_core"},
    {"code": "it", "name": "Italian", "tier": "global_core"},
    {"code": "hi", "name": "Hindi", "tier": "demographic_regional"},
    {"code": "ar", "name": "Modern Standard Arabic", "tier": "demographic_regional"},
    {"code": "bn", "name": "Bengali", "tier": "demographic_regional"},
    {"code": "ur", "name": "Urdu", "tier": "demographic_regional"},
    {"code": "vi", "name": "Vietnamese", "tier": "demographic_regional"},
    {"code": "tr", "name": "Turkish", "tier": "demographic_regional"},
    {"code": "fa", "name": "Persian", "tier": "demographic_regional"},
    {"code": "sw", "name": "Swahili", "tier": "demographic_regional"},
    {"code": "pl", "name": "Polish", "tier": "european_academic"},
]


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_section_hashes(text: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    current_title = "preamble"
    current_lines: List[str] = []
    in_code_block = False
    seen_titles: Dict[str, int] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            current_lines.append(line)
            continue
        if not in_code_block:
            m = re.match(r"^(#{1,3})\s+(.+)$", line)
            if m:
                if current_lines:
                    sec_content = "\n".join(current_lines).strip()
                    sections[current_title] = compute_sha256(sec_content)
                    current_lines = []
                raw_title = m.group(2).strip()
                seen_titles[raw_title] = seen_titles.get(raw_title, 0) + 1
                if seen_titles[raw_title] > 1:
                    current_title = f"{raw_title} (part {seen_titles[raw_title]})"
                else:
                    current_title = raw_title
                continue
        current_lines.append(line)
    if current_lines:
        sec_content = "\n".join(current_lines).strip()
        sections[current_title] = compute_sha256(sec_content)
    return sections


def discover_canonical_documents() -> List[Dict[str, Any]]:
    docs = []

    # 1. Root documents (7 canonical documents)
    docs.append({
        "doc_id": "doc_root_readme",
        "canonical_title": "Academic Research Kernel Readme",
        "source_path": "README.md",
        "source_locale": "en",
        "genre": "user_facing_documentation",
        "aidetox_intensity": "strong",
    })
    docs.append({
        "doc_id": "doc_root_identity",
        "canonical_title": "Repository Identity and Scope",
        "source_path": "REPOSITORY-IDENTITY.md",
        "source_locale": "zh-Hans",
        "genre": "technical_and_schema_specifications",
        "aidetox_intensity": "medium",
    })
    docs.append({
        "doc_id": "doc_root_changelog",
        "canonical_title": "Changelog and Release Manifest",
        "source_path": "CHANGELOG.md",
        "source_locale": "zh-Hans",
        "genre": "historical_and_audit_records",
        "aidetox_intensity": "audit_safe",
    })
    docs.append({
        "doc_id": "doc_root_contributing",
        "canonical_title": "Contributing Guidelines",
        "source_path": "CONTRIBUTING.md",
        "source_locale": "en",
        "genre": "user_facing_documentation",
        "aidetox_intensity": "strong",
    })
    docs.append({
        "doc_id": "doc_root_license_application",
        "canonical_title": "License Application Scope",
        "source_path": "LICENSE-APPLICATION.md",
        "source_locale": "en",
        "genre": "historical_and_audit_records",
        "aidetox_intensity": "audit_safe",
    })
    docs.append({
        "doc_id": "doc_root_license_history",
        "canonical_title": "License History and Terminal Snapshots",
        "source_path": "LICENSE-HISTORY.md",
        "source_locale": "en",
        "genre": "historical_and_audit_records",
        "aidetox_intensity": "audit_safe",
    })
    docs.append({
        "doc_id": "doc_root_source_lineage",
        "canonical_title": "Source Lineage and Intellectual Predecessors",
        "source_path": "SOURCE-LINEAGE.md",
        "source_locale": "en",
        "genre": "historical_and_audit_records",
        "aidetox_intensity": "audit_safe",
    })

    # 2. Skills, References, and Skill-internal documentation
    skills_dir = ROOT / "skills"
    for s_dir in sorted(skills_dir.iterdir()):
        if s_dir.is_dir() and (s_dir / "SKILL.md").exists():
            s_name = s_dir.name
            docs.append({
                "doc_id": f"doc_skill_{s_name.replace('-', '_')}",
                "canonical_title": f"{s_name} Skill Specification",
                "source_path": f"skills/{s_name}/SKILL.md",
                "source_locale": "en" if s_name == "decision-ledger" else "zh-Hans",
                "genre": "user_facing_documentation",
                "aidetox_intensity": "strong",
            })
            ref_dir = s_dir / "references"
            if ref_dir.is_dir():
                for r_file in sorted(ref_dir.glob("*.md")):
                    r_stem = r_file.stem
                    docs.append({
                        "doc_id": f"doc_ref_{s_name.replace('-', '_')}_{r_stem.replace('-', '_')}",
                        "canonical_title": f"{s_name} Reference: {r_stem}",
                        "source_path": f"skills/{s_name}/references/{r_file.name}",
                        "source_locale": "zh-Hans",
                        "genre": "user_facing_documentation",
                        "aidetox_intensity": "strong",
                    })
            s_docs_dir = s_dir / "docs"
            if s_docs_dir.is_dir():
                for sd_file in sorted(s_docs_dir.glob("*.md")):
                    sd_stem = sd_file.stem
                    docs.append({
                        "doc_id": f"doc_{s_name.replace('-', '_')}_{sd_stem.replace('-', '_')}",
                        "canonical_title": f"{s_name} Document: {sd_stem}",
                        "source_path": f"skills/{s_name}/docs/{sd_file.name}",
                        "source_locale": "zh-Hans",
                        "genre": "technical_and_schema_specifications",
                        "aidetox_intensity": "medium",
                    })

    # 3. Docs directory (10 canonical documents)
    docs_dir = ROOT / "docs"
    for d_file in sorted(docs_dir.glob("*.md")):
        d_stem = d_file.stem
        if d_stem in ["pain-atlas-v0.zh", "research-plan-v0.zh"]:
            continue  # localized counterparts of pain-atlas-v0.en and research-plan-v0.en
        docs.append({
            "doc_id": f"doc_{d_stem.replace('-', '_').replace('.', '_')}",
            "canonical_title": f"Documentation: {d_stem}",
            "source_path": f"docs/{d_file.name}",
            "source_locale": "en" if "en" in d_stem or "scfabric" in d_stem else "zh-Hans",
            "genre": "research_plans_and_evaluations" if "plan" in d_stem or "roadmap" in d_stem else "technical_and_schema_specifications",
            "aidetox_intensity": "medium",
        })

    for sub in ["standards", "terminology"]:
        sub_readme = docs_dir / sub / "README.md"
        if sub_readme.exists():
            docs.append({
                "doc_id": f"doc_{sub}_readme",
                "canonical_title": f"{sub.capitalize()} Registry Documentation",
                "source_path": f"docs/{sub}/README.md",
                "source_locale": "en",
                "genre": "technical_and_schema_specifications",
                "aidetox_intensity": "medium",
            })

    return docs


def resolve_localized_path(item: Dict[str, Any], loc: str) -> str:
    """Resolve standard physical file path for a localized counterpart."""
    src = item["source_path"]
    if item["doc_id"] == "doc_root_readme":
        if loc == "zh-Hans":
            return "README.zh-Hans.md"
        elif loc == "zh-Hant":
            return "README.zh-Hant.md"
        elif (ROOT / f"README.{loc}.md").is_file():
            return f"README.{loc}.md"
        else:
            return f"i18n/{loc}/README.md"
    elif src == "docs/pain-atlas-v0.en.md" and loc == "zh-Hans":
        return "docs/pain-atlas-v0.zh.md"
    elif src == "docs/research-plan-v0.en.md" and loc == "zh-Hans":
        return "docs/research-plan-v0.zh.md"
    elif src.startswith("docs/"):
        base_name = src.replace("docs/", "")
        return f"i18n/{loc}/docs/{base_name}"
    else:
        return f"i18n/{loc}/{src}"


def verify_content_parity_admission(doc_item: Dict[str, Any], loc: str, loc_file: Path) -> List[str]:
    """Verify that a localized file meets minimum factual and structural parity before admission as current."""
    issues = []
    src_file = ROOT / doc_item["source_path"]
    if not src_file.is_file() or not loc_file.is_file():
        return ["missing file"]
    loc_text = loc_file.read_text(encoding="utf-8")
    src_text = src_file.read_text(encoding="utf-8")

    # 1. Code blocks parity check
    src_fences = len(re.findall(r"^```", src_text, re.M))
    loc_fences = len(re.findall(r"^```", loc_text, re.M))
    if loc_fences < src_fences:
        issues.append(f"code fence count deficit: expected at least {src_fences}, got {loc_fences}")

    # 2. For READMEs: check that all 13 skill paths are present and content length is substantial
    if doc_item["doc_id"] == "doc_root_readme":
        for s_dir in sorted((ROOT / "skills").iterdir()):
            if s_dir.is_dir() and (s_dir / "SKILL.md").exists():
                skill_id = f"skills/{s_dir.name}"
                if skill_id not in loc_text:
                    issues.append(f"missing skill anchor: '{skill_id}'")
        if len(loc_text) < len(src_text) * 0.45:
            issues.append(f"insufficient content length: {len(loc_text)} bytes vs {len(src_text)} bytes")

    return issues


def build_manifest(certify_paths: Optional[List[str]] = None, certify_all_existing: bool = False) -> Dict[str, Any]:
    # Load previous manifest if available
    prev_manifest: Dict[str, Any] = {}
    prev_docs: Dict[str, Dict[str, Any]] = {}
    if MANIFEST_PATH.is_file():
        try:
            prev_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            for d in prev_manifest.get("documents", []):
                prev_docs[d["doc_id"]] = d
        except Exception:
            pass

    canonical_docs = discover_canonical_documents()
    doc_entries = []

    counts = {
        "canonical_current": 0,
        "localized_current": 0,
        "localized_stale": 0,
        "queued_for_generation": 0,
    }

    for item in canonical_docs:
        src_path = ROOT / item["source_path"]
        if not src_path.is_file():
            continue
        text = src_path.read_text(encoding="utf-8")
        src_sha = compute_sha256(text)
        sec_hashes = extract_section_hashes(text)

        prev_doc_entry = prev_docs.get(item["doc_id"])
        prev_instances = prev_doc_entry.get("localized_instances", {}) if prev_doc_entry else {}

        instances: Dict[str, Any] = {}
        for loc_info in TARGET_LOCALES:
            loc = loc_info["code"]
            if loc == item["source_locale"]:
                instances[loc] = {
                    "path": item["source_path"],
                    "status": "canonical_current",
                    "localized_file_sha256": src_sha,
                    "translated_from_source_sha256": src_sha,
                    "translated_from_section_hashes": sec_hashes,
                    "stale_sections": [],
                    "last_verified": "2026-09-19",
                }
                counts["canonical_current"] += 1
                continue

            loc_path = resolve_localized_path(item, loc)
            full_loc_path = ROOT / loc_path
            prev_inst = prev_instances.get(loc)

            if full_loc_path.is_file():
                loc_text = full_loc_path.read_text(encoding="utf-8")
                loc_sha = compute_sha256(loc_text)

                should_certify = (
                    certify_all_existing
                    or (certify_paths and loc_path in certify_paths)
                )

                admission_issues = verify_content_parity_admission(item, loc, full_loc_path)

                if should_certify and not admission_issues:
                    trans_src_sha = src_sha
                    trans_sec_hashes = sec_hashes
                    status = "localized_current"
                    stale_sections: List[str] = []
                else:
                    trans_src_sha = prev_inst.get("translated_from_source_sha256") if prev_inst else None
                    trans_sec_hashes = prev_inst.get("translated_from_section_hashes") if prev_inst else {}
                    if trans_src_sha == src_sha and not admission_issues:
                        status = "localized_current"
                        stale_sections = []
                    else:
                        status = "localized_stale"
                        stale_sections = [
                            sec for sec, h in sec_hashes.items()
                            if h != (trans_sec_hashes or {}).get(sec)
                        ]
                        for sec in (trans_sec_hashes or {}):
                            if sec not in sec_hashes:
                                stale_sections.append(f"removed: {sec}")
                        for iss in admission_issues:
                            stale_sections.append(f"admission_deficit: {iss}")

                instances[loc] = {
                    "path": loc_path,
                    "status": status,
                    "localized_file_sha256": loc_sha,
                    "translated_from_source_sha256": trans_src_sha,
                    "translated_from_section_hashes": trans_sec_hashes,
                    "stale_sections": stale_sections,
                    "last_verified": "2026-09-19",
                }
                counts[status] += 1
            else:
                instances[loc] = {
                    "path": loc_path,
                    "status": "queued_for_generation",
                    "localized_file_sha256": None,
                    "translated_from_source_sha256": None,
                    "translated_from_section_hashes": None,
                    "stale_sections": [],
                    "last_verified": "2026-09-19",
                }
                counts["queued_for_generation"] += 1

        doc_entries.append({
            "doc_id": item["doc_id"],
            "canonical_title": item["canonical_title"],
            "source_path": item["source_path"],
            "source_locale": item["source_locale"],
            "source_sha256": src_sha,
            "section_hashes": sec_hashes,
            "genre": item["genre"],
            "aidetox_intensity": item["aidetox_intensity"],
            "localized_instances": instances,
        })

    manifest_data = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "version": "2.1.0",
        "title": "Multilingual Scholarly Documentation Synchronization Manifest",
        "description": "Cryptographically authenticated synchronization manifest tracking whole-file SHA-256 and section-level hashes for all 53 canonical documents across 21 locales.",
        "governing_registries": {
            "standards_registry_version": "1.1.0",
            "terminology_registry_version": "2.0.0",
            "aidetox_contract_version": "1.0.0",
        },
        "target_locales": TARGET_LOCALES,
        "total_canonical_documents": len(doc_entries),
        "total_theoretical_instances": len(doc_entries) * len(TARGET_LOCALES),
        "status_summary": counts,
        "documents": doc_entries,
    }
    return manifest_data


def main():
    parser = argparse.ArgumentParser(description="Deterministic Multilingual Documentation Synchronization Engine.")
    parser.add_argument("--certify", nargs="*", help="Mark specific localized paths as synchronized with current source.")
    parser.add_argument("--certify-all-existing", action="store_true", help="Certify all currently existing localized files against current canonical source.")
    parser.add_argument("--check", action="store_true", help="Check manifest validity without modifying files.")
    args = parser.parse_args()

    if args.check:
        if not MANIFEST_PATH.is_file():
            print("ERROR: manifest.json does not exist.")
            sys.exit(1)
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        errors = []
        for doc in manifest.get("documents", []):
            src_file = ROOT / doc["source_path"]
            if not src_file.is_file():
                errors.append(f"Missing source file: {doc['source_path']}")
                continue
            cur_sha = compute_sha256(src_file.read_text(encoding="utf-8"))
            if cur_sha != doc["source_sha256"]:
                errors.append(f"Stale source SHA for: {doc['source_path']}")
            for loc, inst in doc.get("localized_instances", {}).items():
                if inst["status"] in ("localized_current", "localized_stale"):
                    loc_file = ROOT / inst["path"]
                    if not loc_file.is_file():
                        errors.append(f"Missing localized file: {inst['path']}")
                    else:
                        cur_loc_sha = compute_sha256(loc_file.read_text(encoding="utf-8"))
                        if cur_loc_sha != inst["localized_file_sha256"]:
                            errors.append(f"Localized file content changed without manifest update: {inst['path']}")
        if errors:
            print(f"Manifest check FAILED with {len(errors)} errors:")
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)
        print("Manifest check PASSED: all sources and localized instances match registered SHA-256 digests.")
        sys.exit(0)

    manifest = build_manifest(certify_paths=args.certify, certify_all_existing=args.certify_all_existing)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = manifest["status_summary"]
    print(f"Successfully generated {MANIFEST_PATH.relative_to(ROOT)} with {manifest['total_canonical_documents']} canonical documents across 21 locales.")
    print(f"Status breakdown: canonical_current={summary['canonical_current']}, localized_current={summary['localized_current']}, localized_stale={summary['localized_stale']}, queued_for_generation={summary['queued_for_generation']}.")


if __name__ == "__main__":
    main()
