---
name: read-nix-docs
description: Search and read the Nixpkgs manual, NixOS options, and Home Manager options.
---

# Read Nix Docs

Use `read-nix-docs` to search and read documentation from the Nixpkgs Manual, NixOS and Home Manager options.

## When to use

Use this tool when:

- Answering questions about Nixpkgs packaging, build helpers, hooks, language ecosystems, `stdenv`, overlays, or contribution docs.
- Looking up the type, default, example, or description of a NixOS option.
- Looking up the type, default, example, or description of a Home Manager option.
- You need exact documentation rather than an answer from memory.

Do not use this tool for:

- Package search across nixpkgs package attributes. Use package search tools or `nix search` for that.
- Evaluating Nix expressions or checking build results.
- Options from third-party NixOS or Home Manager modules.

## Nixpkgs manual

Search for relevant sections:

```bash
read-nix-docs nixpkgs-manual search QUERY --limit 5
```

List all known section ids:

```bash
read-nix-docs nixpkgs-manual index
```

List subsections below a known section:

```bash
read-nix-docs nixpkgs-manual index python
```

Include titles in index output:

```bash
read-nix-docs nixpkgs-manual index python --titles
```

Get clean markdown for a section:

```bash
read-nix-docs nixpkgs-manual get SECTION_ID
```

## NixOS options

Search option names, descriptions, and types:

```bash
read-nix-docs nixos-options search nginx virtual host --limit 5
```

Get one exact option as Markdown:

```bash
read-nix-docs nixos-options get services.nginx.enable
```

## Home Manager options

Search option names, descriptions, and types:

```bash
read-nix-docs home-manager-docs search bash completion --limit 5
```

Get one exact option as Markdown:

```bash
read-nix-docs home-manager-docs get programs.bash.enable
```

## Recommended workflow

1. Start with `search` using the user's terms.
2. Use `get` with the exact section id or option name from the result you deem more relevant.
3. For the Nixpkgs manual, use `index SECTION_ID --titles` when you need to inspect nearby subsections.
4. Base the answer on the returned Markdown.