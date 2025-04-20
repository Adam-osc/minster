{ stdenv
, darwin
, fetchFromGitHub
, buildPythonPackage
, rustPlatform
}:

buildPythonPackage rec {
  pname = "toy-ibf";
  version = "0e1832fd351891677ab97a26a69c7b5cbcb8cf77";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "Adam-osc";
    repo = pname;
    rev = version;
    hash = "sha256-5hgzjD46UKdq1BARQ5Reqhteny/6xdEeOBl+cvydsUA=";
  };

  cargoDeps = rustPlatform.fetchCargoTarball {
    inherit src;
    hash = "sha256-ABCnjhGp0AONkXtpGB/Hcn52ofxmaD5GbViYEAHlIOE=";
  };
  buildInputs = (if stdenv.hostPlatform.isDarwin then
                   [ darwin.libiconv ]
                 else
                   [  ]);
  nativeBuildInputs = with rustPlatform; [
    cargoSetupHook
    maturinBuildHook
  ];
  pythonImportsCheck = [ "interleaved_bloom_filter" ];
}
