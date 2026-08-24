from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from read_nix_docs import run
from read_nix_docs.option_docs import (
    find_option,
    format_option_markdown,
    load_options,
    search_options,
)


class OptionDocsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.options_file = Path(self.tempdir.name) / "options.json"
        self.options_file.write_text(
            json.dumps(
                {
                    "programs.bash.enable": {
                        "declarations": [
                            {
                                "name": "modules/programs/bash.nix",
                                "url": "https://example.test/bash.nix",
                            }
                        ],
                        "default": {
                            "_type": "literalExpression",
                            "text": "false",
                        },
                        "description": "Whether to enable Bash.",
                        "example": True,
                        "loc": ["programs", "bash", "enable"],
                        "readOnly": False,
                        "type": "boolean",
                    },
                    "services.shell-manager.package": {
                        "declarations": ["modules/services/shell-manager.nix"],
                        "description": "Package used by the shell manager service.",
                        "readOnly": True,
                        "relatedPackages": "- `pkgs.bash`",
                        "type": "package",
                    },
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_load_and_find_options(self) -> None:
        options = load_options(self.options_file)

        self.assertEqual(len(options), 2)
        self.assertEqual(
            find_option(options, "PROGRAMS.BASH.ENABLE").name,
            "programs.bash.enable",
        )

    def test_search_prefers_exact_name_and_searches_descriptions(self) -> None:
        options = load_options(self.options_file)

        exact = search_options(options, "programs.bash.enable", 5)
        description = search_options(options, "shell manager service", 5)
        mixed_fields = search_options(options, "bash boolean", 5)

        self.assertEqual(exact[0][1].name, "programs.bash.enable")
        self.assertEqual(description[0][1].name, "services.shell-manager.package")
        self.assertEqual(mixed_fields[0][1].name, "programs.bash.enable")

    def test_markdown_renders_literals_metadata_and_declarations(self) -> None:
        option = find_option(load_options(self.options_file), "programs.bash.enable")

        output = format_option_markdown(option)

        self.assertIn("# `programs.bash.enable`", output)
        self.assertIn("**Type:** boolean", output)
        self.assertIn("```nix\nfalse\n```", output)
        self.assertIn("```json\ntrue\n```", output)
        self.assertIn(
            "[`modules/programs/bash.nix`](https://example.test/bash.nix)", output
        )

    def test_both_option_corpora_use_the_shared_commands(self) -> None:
        for corpus in ("nixos-options", "home-manager-docs"):
            with self.subTest(corpus=corpus):
                stdout = io.StringIO()
                status = run(
                    [
                        corpus,
                        "--options-file",
                        str(self.options_file),
                        "search",
                        "bash",
                        "--limit",
                        "1",
                    ],
                    stdout=stdout,
                    stderr=io.StringIO(),
                )

                self.assertEqual(status, 0)
                self.assertIn("1. programs.bash.enable", stdout.getvalue())

    def test_get_command_prints_markdown(self) -> None:
        stdout = io.StringIO()
        status = run(
            [
                "home-manager-docs",
                "--options-file",
                str(self.options_file),
                "get",
                "programs.bash.enable",
            ],
            stdout=stdout,
            stderr=io.StringIO(),
        )

        self.assertEqual(status, 0)
        self.assertIn("Whether to enable Bash.", stdout.getvalue())

    def test_missing_option_returns_one(self) -> None:
        stderr = io.StringIO()
        status = run(
            [
                "nixos-options",
                "--options-file",
                str(self.options_file),
                "get",
                "missing.option",
            ],
            stdout=io.StringIO(),
            stderr=stderr,
        )

        self.assertEqual(status, 1)
        self.assertIn("error: option not found: missing.option", stderr.getvalue())

    def test_malformed_json_returns_two(self) -> None:
        self.options_file.write_text("not json", encoding="utf-8")
        stderr = io.StringIO()

        status = run(
            [
                "nixos-options",
                "--options-file",
                str(self.options_file),
                "search",
                "bash",
            ],
            stdout=io.StringIO(),
            stderr=stderr,
        )

        self.assertEqual(status, 2)
        self.assertIn("error: invalid options JSON", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
