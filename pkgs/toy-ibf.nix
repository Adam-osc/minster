{ stdenv
, darwin
, fetchFromGitHub
, buildPythonPackage
, rustPlatform
}:

buildPythonPackage rec {
  pname = "toy-ibf";
  version = "bb6088dd3cc71c4522627813052a462629c1fa51";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "Adam-osc";
    repo = pname;
    rev = version;
    hash = "sha256-WXW2PwR2KhasYGjKftv0uOvvtWDC6pWAG2+zfrKA8iA=";
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
