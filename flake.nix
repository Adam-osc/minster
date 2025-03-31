{
  description = "Real-time DNA sequencing for minION.";

  inputs = {
    # this revision has grpcio built with protobuf version 4
    # overriding protobuf version for grpcio and then building it is also an option
    nixpkgs.url = "github:NixOS/nixpkgs/47c1824c261a343a6acca36d168a0a86f0e66292";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };
        python = pkgs.python312;
        pythonPackages = pkgs.python312Packages;
        zran = import ./pkgs/zran.nix {
          stdenv = pkgs.stdenv;
          fetchFromGitHub = pkgs.fetchFromGitHub;
          pkg-config = pkgs.pkg-config;
          zlib = pkgs.zlib;
          inherit python;
        };

        packages = {
          mappy = import ./pkgs/mappy.nix {
            buildPythonPackage = pythonPackages.buildPythonPackage;
            fetchPypi = pythonPackages.fetchPypi;
            setuptools = pythonPackages.setuptools;
            wheel = pythonPackages.wheel;
            cython = pythonPackages.cython;
            zlib = pkgs.zlib;
          };
          minknow_api = import ./pkgs/minknow-api.nix {
            buildPythonPackage = pythonPackages.buildPythonPackage;
            fetchPypi = pythonPackages.fetchPypi;
            setuptools = pythonPackages.setuptools;
            grpcio = pythonPackages.grpcio;
            numpy = pythonPackages.numpy;
            protobuf = pythonPackages.protobuf;
            packaging = pythonPackages.packaging;
            pyrfc3339 = pythonPackages.pyrfc3339;
          };
          ont_pybasecall_client_lib = import ./pkgs/ont-pybasecall-client-lib.nix {
            stdenv = pkgs.stdenv;
            dynLibsPatcher = if pkgs.stdenv.hostPlatform.isLinux then pkgs.autoPatchelfHook else pkgs.fixDarwinDylibNames;
            buildPythonPackage = pythonPackages.buildPythonPackage;
            fetchPypi = pythonPackages.fetchPypi;
            numpy = pythonPackages.numpy;
            pythonVersion = python.pythonVersion;
          };
          pyfastx = import ./pkgs/pyfastx.nix {
            buildPythonPackage = pythonPackages.buildPythonPackage;
            fetchPypi = pythonPackages.fetchPypi;
            setuptools = pythonPackages.setuptools;
            pkg-config = pkgs.pkg-config;
            zlib = pkgs.zlib;
            inherit zran;
            sqlite = pkgs.sqlite;
          };
          interleaved_bloom_filter = import ./pkgs/toy-ibf.nix {
            stdenv = pkgs.stdenv;
            darwin = if pkgs.stdenv.hostPlatform.isDarwin then pkgs.darwin else null;
            fetchFromGitHub = pkgs.fetchFromGitHub;
            buildPythonPackage = pythonPackages.buildPythonPackage;
            rustPlatform = pkgs.rustPlatform;
          };
        };
        pythonEnv = python.withPackages
          (ps: [ packages.mappy
                 packages.minknow_api
                 packages.ont_pybasecall_client_lib
                 packages.pyfastx
                 packages.interleaved_bloom_filter
                 pythonPackages.numpy
                 pythonPackages.watchdog
                 pythonPackages.pydantic
                 pythonPackages.pydantic-settings
               ]);
      in
        {
          devShell = pkgs.mkShell {
            nativeBuildInputs = [ pythonEnv ];
          };
        });
}
