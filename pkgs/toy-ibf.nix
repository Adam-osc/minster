{ fetchFromGitHub
, buildPythonPackage
, rustPlatform
}:

buildPythonPackage rec {
  pname = "toy-ibf";
  version = "e1da1ff0e4193386c2ab98eee301581b66a37e9f";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "Adam-osc";
    repo = pname;
    rev = version;
    hash = "sha256-4UT/KqPKmMaAXnNS2x7ZNrYUMzqRDp3F7muKCF3yXfk=";
  };

  cargoDeps = rustPlatform.fetchCargoTarball {
    inherit src;
    hash = "sha256-VfqW5CXvJiN8CGlWR1MAIezmAGBMch8ljKzwxlzF3Sk=";
  };
  nativeBuildInputs = with rustPlatform; [
    cargoSetupHook
    maturinBuildHook
  ];
  pythonImportsCheck = [ "interleaved_bloom_filter" ];
}
