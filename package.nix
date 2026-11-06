{
  lib,
  callPackage,
  python3Packages,
  runCommand,
  nixpkgs,
  nixosOptions,
  homeManagerOptions,
}:

let
  # Referencing nixpkgs/doc directly would retain the whole Nixpkgs source.
  manualSource =
    runCommand "nixpkgs-manual-source" { allowedReferences = [ ]; } # sh
      ''
        cp -R ${nixpkgs}/doc "$out"
      '';
in
python3Packages.buildPythonApplication (finalAttrs: {
  pname = "read-nix-docs";
  version = (lib.importTOML ./pyproject.toml).project.version;

  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./src
      ./tests
    ];
  };

  pyproject = true;
  build-system = with python3Packages; [
    setuptools
    wheel
  ];

  postPatch = # sh
    ''
      substituteInPlace src/read_nix_docs/__init__.py \
        --replace-fail '@nixpkgs_doc@' '${manualSource}' \
        --replace-fail '@nixos_options_json@' '${nixosOptions}/share/doc/nixos/options.json' \
        --replace-fail '@home_manager_options_json@' '${homeManagerOptions}/share/doc/home-manager/options.json'
    '';

  doCheck = true;
  checkPhase = # sh
    ''
      runHook preCheck
      python -m unittest discover -s tests
      runHook postCheck
    '';
  pythonImportsCheck = [ "read_nix_docs" ];

  passthru.tests.corpora = callPackage ./test.nix { read-nix-docs = finalAttrs.finalPackage; };

  meta = {
    description = "Search and read Nixpkgs, NixOS and Home Manager documentation offline";
    homepage = "https://github.com/billy4479/read-nix-docs";
    mainProgram = "read-nix-docs";
  };
})
