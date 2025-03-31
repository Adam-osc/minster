{ stdenv
, dynLibsPatcher
, buildPythonPackage
, fetchPypi
# dependencies
, numpy
# cross-cutting
, pythonVersion
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
      x86_64-linux = "sha256-0Cw02aNu4bHkhsvTqApsdR1fOeFvNNd78bZTcmUoKT0=";
      aarch64-linux = "";
      x86_64-darwin = "";
      aarch64-darwin = "sha256-m7co1smRU4HYgmmoqyKwAS1Yxp+h2FomN7gy01DMCCg=";
    };
  };
in
buildPythonPackage rec {
  pname = "ont_pybasecall_client_lib";
  version = "7.4.12";
  format = "wheel";

  src = fetchPypi {
    inherit pname version format;
    hash = digests."${cpTag}"."${stdenv.system}";
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
