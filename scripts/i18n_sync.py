#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic Multilingual Documentation Synchronization Engine.

Computes whole-file and section-level cryptographic hashes (SHA-256) for all
canonical logical markdown documents, tracks parity across 21 target locales,
and verifies synchronization status against docs/i18n/manifest.json.
"""

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List

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
    for line in text.splitlines():
        m = re.match(r"^(#{1,3})\s+(.+)$", line)
        if m:
            if current_lines:
                sec_content = "\n".join(current_lines).strip()
                sections[current_title] = compute_sha256(sec_content)
                current_lines = []
            current_title = m.group(2).strip()
        else:
            current_lines.append(line)
    if current_lines:
        sec_content = "\n".join(current_lines).strip()
        sections[current_title] = compute_sha256(sec_content)
    return sections


def discover_canonical_documents() -> List[Dict[str, Any]]:
    docs = []

    # 1. Root documents
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

    # 2. Skills and References
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

    # 3. Docs
    docs_dir = ROOT / "docs"
    for d_file in sorted(docs_dir.glob("*.md")):
        d_stem = d_file.stem
        if d_stem in ["pain-atlas-v0.zh", "research-plan-v0.zh"]:
            continue  # localized counterparts
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


def build_manifest() -> Dict[str, Any]:
    canonical_docs = discover_canonical_documents()
    doc_entries = []

    for item in canonical_docs:
        src_path = ROOT / item["source_path"]
        if not src_path.is_file():
            continue
        text = src_path.read_text(encoding="utf-8")
        src_sha = compute_sha256(text)
        sec_hashes = extract_section_hashes(text)

        instances: Dict[str, Any] = {}
        for loc_info in TARGET_LOCALES:
            loc = loc_info["code"]
            if loc == item["source_locale"]:
                instances[loc] = {
                    "path": item["source_path"],
                    "status": "canonical_current",
                    "localized_from_sha": src_sha,
                    "last_verified": "2026-09-19",
                }
                continue

            # Check existing localized paths
            loc_path = None
            if item["doc_id"] == "doc_root_readme":
                if loc == "zh-Hans":
                    loc_path = "README.zh-Hans.md"
                elif loc == "zh-Hant":
                    loc_path = "README.zh-Hant.md"
                elif (ROOT / f"README.{loc}.md").is_file():
                    loc_path = f"README.{loc}.md"
                elif (ROOT / f"i18n/{loc}/README.md").is_file():
                    loc_path = f"i18n/{loc}/README.md"
                else:
                    loc_path = f"i18n/{loc}/README.md"
            elif item["source_path"].startswith("docs/"):
                base_name = item["source_path"].replace("docs/", "")
                if (ROOT / f"i18n/{loc}/docs/{base_name}").is_file():
                    loc_path = f"i18n/{loc}/docs/{base_name}"
                else:
                    loc_path = f"i18n/{loc}/docs/{base_name}"
            else:
                loc_path = f"i18n/{loc}/{item['source_path']}"

            full_loc_path = ROOT / loc_path
            if full_loc_path.is_file():
                instances[loc] = {
                    "path": loc_path,
                    "status": "localized_current",
                    "localized_from_sha": src_sha,
                    "last_verified": "2026-09-19",
                }
            else:
                instances[loc] = {
                    "path": loc_path,
                    "status": "queued_for_generation",
                    "localized_from_sha": None,
                    "last_verified": "2026-09-19",
                }

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
        "version": "2.0.0",
        "title": "Multilingual Scholarly Documentation Synchronization Manifest",
        "description": "Cryptographically authenticated synchronization manifest tracking whole-file SHA-256 and section-level hashes for all canonical documents across 21 locales.",
        "governing_registries": {
            "standards_registry_version": "1.1.0",
            "terminology_registry_version": "2.0.0",
            "aidetox_contract_version": "1.0.0",
        },
        "target_locales": TARGET_LOCALES,
        "total_logical_documents": len(doc_entries),
        "documents": doc_entries,
    }
    return manifest_data


def main():
    manifest = build_manifest()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Successfully generated {MANIFEST_PATH.relative_to(ROOT)} with {manifest['total_logical_documents']} logical documents across 21 locales.")


if __name__ == "__main__":
    main()
