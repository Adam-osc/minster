{ stdenv
, dynLibsPatcher
, buildPythonPackage
, fetchPypi
# dependencies
, numpy
# cross-cutting
, pythonVersion
, version
}:

let
  linuxArch = if stdenv.hostPlatform.linuxArch == "arm64" then "aarch64" else stdenv.hostPlatform.linuxArch;
  platformTag =
    if stdenv.hostPlatform.isLinux then
      "manylinux_2_17_${linuxArch}.manylinux2014_${linuxArch}"
    else if stdenv.system == "x86_64-darwin" then
      "macosx_10_15_x86_64"
    else if stdenv.system == "aarch64-darwin" then
      "macosx_11_0_arm64"
    else
      throw "Unsupported target platform: ${stdenv.hostPlatform}";
  cpTag = "cp${builtins.replaceStrings [ "." ] [ "" ] pythonVersion}";
  digests = {
    cp312 = {
      "7.4.12" = {
        x86_64-linux = "sha256-0Cw02aNu4bHkhsvTqApsdR1fOeFvNNd78bZTcmUoKT0=";
        aarch64-linux = "sha256-d/LA/E3A/iDncYAOu+7tWrrBYA1zdsjHSl2m9u7YOkQ=";
        x86_64-darwin = "sha256-raQd5HwiHRGSkQIt6vXLDFwW+8aVyKkAgavVWOqr0Pg=";
        aarch64-darwin = "sha256-m7co1smRU4HYgmmoqyKwAS1Yxp+h2FomN7gy01DMCCg=";
      };
      "7.6.8" = {
        x86_64-linux = "sha256-Pudx8C0n6yxxum09Oi8W0YD/BOw5DIPr9Tf/vFtfKgI=";
        aarch64-linux = "sha256-tuNTHglPfZuf9xbOG1DnJbdG0eQJxAZO7dRpJpIC4tU=";
        x86_64-darwin = "sha256-IajWkJzlMaWGzK4UW6YgzWnHjzQiacB3YC5gvYvCa8Y=";
        aarch64-darwin = "sha256-j40q4AorwYVS5/nsTnWXqp2JsRZ2sP6Uj4GQDkusCgo=";
      };
    };
  };
in
buildPythonPackage rec {
  pname = "ont_pybasecall_client_lib";
  inherit version;
  format = "wheel";

  src = fetchPypi {
    inherit pname version format;
    hash = digests."${cpTag}"."${version}"."${stdenv.system}";
    dist = cpTag;
    python = cpTag;
    abi = cpTag;
    platform = platformTag;
  };

  nativeBuildInputs = [ dynLibsPatcher ];
  buildInputs = [
    stdenv.cc.cc.lib
  ];
  dependencies = [
    numpy
  ];

  pythonImportsCheck = [ "pybasecall_client_lib" ];
}
