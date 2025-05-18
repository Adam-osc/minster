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
# cross-cutting
, version
}:

let
  digests = {
    "6.2.1" = "sha256-X++FcO7iNFk2b1Rrx6zMupAJeQOifCbAb1eVcxdYaus=";
  };
in
buildPythonPackage rec {
  pname = "minknow_api";
  inherit version;
  pyproject = true;

  src = fetchPypi {
    inherit pname version;
    hash = digests."${version}";
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
