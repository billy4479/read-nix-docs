{ read-nix-docs, runCommand }:

runCommand "read-nix-docs-corpora-test" { nativeBuildInputs = [ read-nix-docs ]; } # sh
  ''
    read-nix-docs nixpkgs-manual get sec-language-go > manual.md
    grep -q buildGoModule manual.md
    read-nix-docs nixos-options get services.openssh.enable > nixos.md
    grep -q services.openssh.enable nixos.md
    read-nix-docs home-manager-docs get home.username > home-manager.md
    grep -q home.username home-manager.md
    touch "$out"
  ''
