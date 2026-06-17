---
name: nix-docs-extractor
description: Use to consult Nixpkgs manual documentation, helps to get information on how to write nix packages.
---

# Nix Docs Extractor

Use `nix-docs-extractor` when you need information from the Nixpkgs manual.

## When To Use

Use this tool when:

- Answering questions about Nixpkgs packaging, build helpers, hooks, language ecosystems, `stdenv`, overlays, configuration, or contribution docs.
- You need exact manual wording or examples from the Nixpkgs documentation.
- You need a stable section id to cite or retrieve later.
- The user asks for relevant Nixpkgs manual sections or documentation snippets.

Do not use this tool for:

- NixOS options, Home Manager options, or other manuals.
- Package search across nixpkgs package attributes. Use package search tools or `nix search` for that.
- Evaluating Nix expressions or checking build results.

## Commands

Search for relevant sections:

```bash
nix-docs-extractor search QUERY --limit 5
```

List all known section ids:

```bash
nix-docs-extractor index
```

List subsections below a known section:

```bash
nix-docs-extractor index python
```

Include titles in index output:

```bash
nix-docs-extractor index python --titles
```

Get clean markdown for a section:

```bash
nix-docs-extractor get SECTION_ID
```

Override the docs root only when working against a local checkout explicitly:

```bash
nix-docs-extractor --docs-root ../../src/nixpkgs/doc search cargoHash
```

## Recommended Workflow

1. Start with `search` using the user’s terms.
2. If results are broad, run `index SECTION_ID --titles` on the likely parent section to inspect its subsections.
3. Use `get SECTION_ID` for the most relevant section.
4. Base answers on the returned markdown, not memory, when exact Nixpkgs manual behavior matters.

## Examples

Find Rust packaging docs:

```bash
nix-docs-extractor search buildRustPackage cargoHash --limit 5
```

Inspect Python manual sections:

```bash
nix-docs-extractor index python --titles
```

Retrieve the Python pytest section:

```bash
nix-docs-extractor get using-pytest
```

Retrieve unfree package configuration docs:

```bash
nix-docs-extractor get sec-allow-unfree
```

Get the first lines of the Python section:

```bash
nix-docs-extractor get python | head
```
