"""Offline SLL identity, application scope and recorded transition regression."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HASH = "f6c982dafe666ceb2b01df4bc4f146e4facbd6f62753b7ae4cfd324f1db7cda6"
EXPECTED_BLOB = "d24b763a2d3ecbc13c21760c60345b8e9adff33d"
REF = "LicenseRef-Source-Lineage-1.0"


class LicenseApplicationTests(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads((ROOT / "SLL-APPLICATION.json").read_text(encoding="utf-8"))

    def test_exact_canonical_bytes(self):
        raw = (ROOT / "LICENSE").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_HASH)
        self.assertEqual(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(), EXPECTED_BLOB)
        self.assertIn("Source Lineage License Version 1.0", raw.decode())
        self.assertIn(REF, raw.decode())

    def test_application_is_rights_limited(self):
        notice = (ROOT / "LICENSE-APPLICATION.md").read_text(encoding="utf-8")
        for term in ("Junfu Shi", "lawfully entitled to license", "more specific", "third-party material", "rights are uncertain", "neither title nor copyrightability", "no express patent grant"):
            self.assertIn(term, notice)
        self.assertIn("not an SPDX-assigned identifier", notice)
        self.assertIn("does not imply OSI approval", notice)

    def test_boundary_records_agree(self):
        history = (ROOT / "LICENSE-HISTORY.md").read_text(encoding="utf-8")
        lineage = (ROOT / "SOURCE-LINEAGE.md").read_text(encoding="utf-8")
        self.assertIn(self.receipt["pre_application_commit"], history)
        self.assertIn(self.receipt["pre_application_commit"], lineage)
        state = self.receipt["boundary_state"]
        if state == "pending-first-commit":
            # Commit A cannot name itself. Only the explicit initial state may be pending.
            self.assertIsNone(self.receipt["application_commit"])
            self.assertIsNone(self.receipt["application_tree"])
            self.assertIn("PENDING", history)
            self.assertIn("PENDING", lineage)
        else:
            self.assertEqual(state, "recorded")
            for field in ("application_commit", "application_tree"):
                value = self.receipt[field]
                self.assertRegex(value, r"^[0-9a-f]{40}$")
                self.assertIn(value, history)
                self.assertIn(value, lineage)
            self.assertNotIn("PENDING", history)
            self.assertNotIn("PENDING", lineage)
        self.assertEqual(self.receipt["license_sha256"], EXPECTED_HASH)
        self.assertEqual(self.receipt["canonical_sll_blob"], EXPECTED_BLOB)
        self.assertTrue(self.receipt["historical_grants_preserved"])
        self.assertTrue(self.receipt["third_party_rights_preserved"])

    def test_application_and_readme_links_resolve(self):
        paths = list(ROOT.glob("README*.md")) + [ROOT / n for n in ("LICENSE-APPLICATION.md", "SOURCE-LINEAGE.md", "LICENSE-HISTORY.md")]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                self.assertTrue((path.parent / target.split("#")[0]).exists(), (path.name, target))
        for path in ROOT.glob("README*.md"):
            text = path.read_text(encoding="utf-8")
            for name in ("LICENSE", "LICENSE-APPLICATION.md", "SOURCE-LINEAGE.md", "LICENSE-HISTORY.md"):
                self.assertIn("](" + name + ")", text, path.name)

    def test_contribution_policy_does_not_assign_by_submission(self):
        path = ROOT / "CONTRIBUTING.md"
        if path.exists():
            text = path.read_text(encoding="utf-8")
            self.assertIn("not accepted by default", text)
            self.assertIn("does not assign copyright or patent rights", text)
            self.assertIn("SLL is not a CLA", text)
            self.assertIn("separate, explicit inbound arrangement", text)

    def test_ce_current_version_localizations_and_prior_proposal(self):
        if self.receipt["repository"] != "xngg1021/context-economics":
            return
        from context_economics import __version__
        self.assertEqual(__version__, "0.7.1")
        self.assertEqual((ROOT / "VERSION").read_text().strip(), __version__)
        paths = list(ROOT.glob("README*.md"))
        self.assertEqual(len(paths), 8)
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("0.7.1", text, path.name)
            self.assertIn("Source Lineage License 1.0", text, path.name)
            self.assertEqual(text.count("<!-- sll-license:start -->"), 1)
            # All product/research text is identical to the approved baseline,
            # allowing only current-version changes and the new license block.
            prior = re.sub(r"\n*<!-- sll-license:start -->.*?<!-- sll-license:end -->\n*", "\n", text, flags=re.S).rstrip() + "\n"
            prior = prior.replace("0.7.1", "0.7.0")
            self.assertEqual(hashlib.sha256(prior.encode()).hexdigest(), self.receipt["readme_product_hashes"][path.name], path.name)
        history = (ROOT / "LICENSE-HISTORY.md").read_text()
        self.assertIn("CLOSED / NOT MERGED / SUPERSEDED", history)
        self.assertIn("never applicable to main through PR #9", history)
        forbidden = "LicenseRef-" + "SJF-SVPL-1.0"
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".py", ".json"} and not any(part in {".git", "__pycache__", "artifacts"} for part in path.parts):
                self.assertNotIn(forbidden, path.read_text(encoding="utf-8"), str(path))

    def test_hermes_mit_boundary_and_upstream_remain_separate(self):
        if self.receipt["repository"] != "xngg1021/hermes-academic-skills":
            return
        history = (ROOT / "LICENSE-HISTORY.md").read_text()
        self.assertIn("retain the permissions already granted under MIT", history)
        self.assertIn("do not have to migrate to SLL", history)
        for path, expected in self.receipt["preserved_mit_files"].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), expected)
        for path, expected in self.receipt["skill_body_hashes"].items():
            text = (ROOT/path).read_text(encoding="utf-8")
            self.assertIn("license: " + REF + "\n", text)
            old = text.replace("license: " + REF + "\n", "license: MIT\n")
            self.assertEqual(hashlib.sha256(old.encode()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
