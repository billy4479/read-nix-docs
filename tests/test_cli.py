from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import read_nix_docs
from read_nix_docs import load_manual, parse_sections, run, search_sections


class ReadNixDocsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.docs_root = Path(self.tempdir.name)
        (self.docs_root / "chapters").mkdir()
        (self.docs_root / "sections").mkdir()
        (self.docs_root / "manual.md.in").write_text(
            "# Manual {#manual}\n"
            "## Version @MANUAL_VERSION@\n"
            "\n"
            "```{=include=} chapters\n"
            "chapters/intro.md\n"
            "```\n",
            encoding="utf-8",
        )
        (self.docs_root / "chapters" / "intro.md").write_text(
            "# Intro {#intro}\n"
            "Intro text about packages.\n"
            "\n"
            "```{=include=} sections\n"
            "../sections/rust.md\n"
            "```\n"
            "\n"
            "## After Rust {#after-rust}\n"
            "Trailing text.\n",
            encoding="utf-8",
        )
        (self.docs_root / "sections" / "rust.md").write_text(
            "## Rust {#rust}\n"
            "Rust build helpers.\n"
            "<!-- source-only comment -->\n"
            "@generated-table@\n"
            "\n"
            "### Cargo hash {#cargo-hash}\n"
            "Use cargoHash for vendored dependencies.\n"
            "\n"
            "```nix\n"
            "# Not a heading {#not-heading}\n"
            "<!-- keep comments in code fences -->\n"
            "@keep-placeholder-in-code@\n"
            "```\n",
            encoding="utf-8",
        )
        (self.docs_root / "generated.md.in").write_text(
            "# Generated Stub {#generated-stub}\nGenerated source fallback.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_load_manual_expands_local_includes_and_substitutes_version(self) -> None:
        text = "".join(line.text for line in load_manual(self.docs_root))

        self.assertIn("## Version unknown", text)
        self.assertIn("## Rust {#rust}", text)
        self.assertIn("### Cargo hash {#cargo-hash}", text)

    def test_load_manual_falls_back_to_md_in_for_generated_sources(self) -> None:
        (self.docs_root / "manual.md.in").write_text(
            "# Manual {#manual}\n\n```{=include=} chapters\ngenerated.md\n```\n",
            encoding="utf-8",
        )

        text = "".join(line.text for line in load_manual(self.docs_root))

        self.assertIn("# Generated Stub {#generated-stub}", text)

    def test_default_docs_root_prefers_nix_patched_docs_root(self) -> None:
        original = read_nix_docs.NIXPKGS_DOCS_ROOT
        try:
            read_nix_docs.NIXPKGS_DOCS_ROOT = self.docs_root

            self.assertEqual(read_nix_docs.default_docs_root(), self.docs_root)
        finally:
            read_nix_docs.NIXPKGS_DOCS_ROOT = original

    def test_parse_sections_extracts_ids_and_boundaries(self) -> None:
        lines = load_manual(self.docs_root)
        sections = parse_sections(lines)
        ids = [section.id for section in sections]

        self.assertEqual(
            ids,
            ["manual", "version-unknown", "intro", "rust", "cargo-hash", "after-rust"],
        )
        cargo = next(section for section in sections if section.id == "cargo-hash")
        cargo_text = "".join(line.text for line in lines[cargo.start : cargo.end])
        self.assertIn("Use cargoHash", cargo_text)
        self.assertIn("# Not a heading", cargo_text)
        self.assertNotIn("Trailing text", cargo_text)

    def test_search_prefers_matching_sections(self) -> None:
        lines = load_manual(self.docs_root)
        sections = parse_sections(lines)
        results = search_sections(sections, lines, "cargoHash", 5)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0][1].id, "cargo-hash")

    def test_search_command_prints_readable_result_blocks(self) -> None:
        stdout = io.StringIO()
        status = run(
            [
                "nixpkgs-manual",
                "--docs-root",
                str(self.docs_root),
                "search",
                "cargoHash",
                "--limit",
                "1",
            ],
            stdout=stdout,
            stderr=io.StringIO(),
        )

        self.assertEqual(status, 0)
        output = stdout.getvalue()
        self.assertIn("1. Cargo hash", output)
        self.assertIn("   id:     cargo-hash", output)
        self.assertIn("   source: sections/rust.md:6", output)
        self.assertIn("   path:   Intro > Rust > Cargo hash", output)

    def test_index_command_lists_section_ids(self) -> None:
        stdout = io.StringIO()
        status = run(
            ["nixpkgs-manual", "--docs-root", str(self.docs_root), "index"],
            stdout=stdout,
            stderr=io.StringIO(),
        )

        self.assertEqual(status, 0)
        self.assertIn("###\tcargo-hash\n", stdout.getvalue())

    def test_index_command_can_list_subsections(self) -> None:
        stdout = io.StringIO()
        status = run(
            [
                "nixpkgs-manual",
                "--docs-root",
                str(self.docs_root),
                "index",
                "rust",
                "--titles",
            ],
            stdout=stdout,
            stderr=io.StringIO(),
        )

        self.assertEqual(status, 0)
        output = stdout.getvalue()
        self.assertIn("###\tcargo-hash\tCargo hash\n", output)
        self.assertNotIn("after-rust", output)

    def test_index_command_reports_missing_section(self) -> None:
        stderr = io.StringIO()
        status = run(
            [
                "nixpkgs-manual",
                "--docs-root",
                str(self.docs_root),
                "index",
                "missing-section",
            ],
            stdout=io.StringIO(),
            stderr=stderr,
        )

        self.assertEqual(status, 1)
        self.assertIn("error: section not found: missing-section", stderr.getvalue())

    def test_get_command_prints_section_markdown(self) -> None:
        stdout = io.StringIO()
        status = run(
            [
                "nixpkgs-manual",
                "--docs-root",
                str(self.docs_root),
                "get",
                "cargo-hash",
            ],
            stdout=stdout,
            stderr=io.StringIO(),
        )

        self.assertEqual(status, 0)
        self.assertIn("### Cargo hash {#cargo-hash}", stdout.getvalue())
        self.assertNotIn("## After Rust", stdout.getvalue())

    def test_get_command_removes_comments_and_unresolved_placeholders(self) -> None:
        stdout = io.StringIO()
        status = run(
            [
                "nixpkgs-manual",
                "--docs-root",
                str(self.docs_root),
                "get",
                "rust",
            ],
            stdout=stdout,
            stderr=io.StringIO(),
        )

        self.assertEqual(status, 0)
        output = stdout.getvalue()
        self.assertNotIn("source-only comment", output)
        self.assertNotIn("@generated-table@", output)
        self.assertIn("<!-- keep comments in code fences -->", output)
        self.assertIn("@keep-placeholder-in-code@", output)


if __name__ == "__main__":
    unittest.main()
