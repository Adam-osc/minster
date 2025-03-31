{ buildPythonPackage
, fetchPypi
# build-system
, setuptools
# dependencies
, grpcio
, numpy
, protobuf
, packaging
, pyrfc3339
}:

buildPythonPackage rec {
  pname = "minknow_api";
  version = "6.2.1";
  pyproject = true;

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-X++FcO7iNFk2b1Rrx6zMupAJeQOifCbAb1eVcxdYaus=";
  };

  build-system = [
    setuptools
  ];
  dependencies = [
    grpcio
    numpy
    protobuf
    packaging
    pyrfc3339
  ];
}
