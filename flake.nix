{
  description = "Real-time DNA sequencing for minION.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/09b35c919d51bc292d9de1351296b609b2dd0a6f";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };

        python = pkgs.python312;
        pythonPackages = pkgs.python312Packages;

        grpcio = import ./packages/grpcio.nix {
          lib = pkgs.lib;
          stdenv = pkgs.stdenv;
          buildPythonPackage = pythonPackages.buildPythonPackage;
          c-ares = pkgs.c-ares;
          cython = pythonPackages.cython;
          fetchPypi = pythonPackages.fetchPypi;
          openssl = pkgs.openssl;
          pkg-config = pkgs.pkg-config;
          protobuf = pythonPackages.protobuf4;
          pythonOlder = pythonPackages.pythonOlder;
          setuptools = pythonPackages.setuptools;
          zlib = pkgs.zlib;
        };
        zran = import ./packages/zran.nix {
          stdenv = pkgs.stdenv;
          fetchFromGitHub = pkgs.fetchFromGitHub;
          pkg-config = pkgs.pkg-config;
          zlib = pkgs.zlib;
          inherit python;
        };

        packages = {
          mappy = import ./packages/mappy.nix {
            buildPythonPackage = pythonPackages.buildPythonPackage;
            fetchPypi = pythonPackages.fetchPypi;
            setuptools = pythonPackages.setuptools;
            wheel = pythonPackages.wheel;
            cython = pythonPackages.cython;
            zlib = pkgs.zlib;
          };
          minknow_api = import ./packages/minknow-api.nix {
            buildPythonPackage = pythonPackages.buildPythonPackage;
            fetchPypi = pythonPackages.fetchPypi;
            setuptools = pythonPackages.setuptools;
            inherit grpcio;
            numpy = pythonPackages.numpy;
            protobuf = pythonPackages.protobuf4;
            packaging = pythonPackages.packaging;
            pyrfc3339 = pythonPackages.pyrfc3339;
            version = "6.2.1";
          };
          ont_pybasecall_client_lib = import ./packages/ont-pybasecall-client-lib.nix {
            stdenv = pkgs.stdenv;
            dynLibsPatcher = if pkgs.stdenv.hostPlatform.isLinux then pkgs.autoPatchelfHook else pkgs.fixDarwinDylibNames;
            buildPythonPackage = pythonPackages.buildPythonPackage;
            fetchPypi = pythonPackages.fetchPypi;
            numpy = pythonPackages.numpy;
            pythonVersion = python.pythonVersion;
            version = "7.6.8";
          };
          pyfastx = import ./packages/pyfastx.nix {
            buildPythonPackage = pythonPackages.buildPythonPackage;
            fetchPypi = pythonPackages.fetchPypi;
            setuptools = pythonPackages.setuptools;
            pkg-config = pkgs.pkg-config;
            zlib = pkgs.zlib;
            inherit zran;
            sqlite = pkgs.sqlite;
          };
          interleaved_bloom_filter = import ./packages/toy-ibf.nix {
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
                 pythonPackages.pandas
                 # pythonPackages.dash
               ]);
      in
        {
          devShell = pkgs.mkShell {
            buildInputs = [ pythonEnv ];
          };
        });
}
