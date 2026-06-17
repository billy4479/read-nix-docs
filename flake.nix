{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        pyPkgs = pkgs.python3.withPackages (
          python-pkgs: with python-pkgs; [
            python-lsp-server
            python-lsp-ruff
          ]
        );
      in
      {
        packages = rec {
          app = pkgs.python3.pkgs.buildPythonApplication {
            pname =
              if builtins.pathExists ./pyproject.toml then
                (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.name
              else
                "app";
            version = "0.1.0";
            src = ./.;
            pyproject = true;

            nativeBuildInputs = with pkgs.python3.pkgs; [
              setuptools
              wheel
            ];
          };
          default = app;
        };

        devShells.default = pkgs.mkShell {
          nativeBuildInputs = [ pyPkgs ];

          packages = with pkgs; [
            ruff

            (pkgs.writeShellScriptBin "init" ''
              set -eu

              if [ -d .git ]; then
                echo "Refusing to initialize: .git already exists" >&2
                exit 1
              fi

              project_name="$(basename "$PWD")"
              module_name="$(printf '%s' "$project_name" | tr '-' '_' | tr -c '[:alnum:]_' '_')"

              mkdir -p "src/$module_name"

              cat > pyproject.toml <<EOF
              [project]
              name = "$project_name"
              version = "0.1.0"
              requires-python = ">=3.12"

              [project.scripts]
              $project_name = "$module_name:main"

              [build-system]
              requires = ["setuptools", "wheel"]
              build-backend = "setuptools.build_meta"
              EOF

              cat > "src/$module_name/__init__.py" <<EOF
              def main():
                  print("Hello from $project_name")
              EOF

              cat > "src/$module_name/__main__.py" <<EOF
              from . import main

              if __name__ == "__main__":
                  main()
              EOF

              git init
              git add .
              git commit -m "Initial commit"
            '')
          ];
        };
      }
    );
}
