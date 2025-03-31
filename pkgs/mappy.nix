{ buildPythonPackage
, fetchPypi
# build-system
, setuptools
, wheel
, cython
# buildInputs
, zlib
}:

buildPythonPackage rec {
  pname = "mappy";
  version = "2.28";
  pyproject = true;

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-Dr96XWK9Zo9UVgKCFeJhduGAymgWGsGNT3tIBFSEzrs=";
  };

  build-system = [
    setuptools
    wheel
    cython
  ];
  buildInputs = [
    zlib
  ];

  pythonImportsCheck = [ "mappy" ];
}
