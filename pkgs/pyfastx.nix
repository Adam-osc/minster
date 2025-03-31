{ buildPythonPackage
, fetchPypi
# build-system
, setuptools
# nativeBuildInputs
, pkg-config
# buildInputs
, zlib
, zran
, sqlite
}:

buildPythonPackage rec {
  pname = "pyfastx";
  version = "2.2.0";

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-gPFYWgwP0CHR4AkexCdaK+1lh2M79pFldI/xpUH9zCc=";
  };

  nativeBuildInputs = [
    pkg-config
  ];
  build-system = [
    setuptools
  ];
  buildInputs = [
    zlib
    zran
    sqlite
  ];

  doCheck = false;
  pythonImportsCheck = [ "pyfastx" ];

  patches = [ ./no-requests.patch ];
  preBuild = ''
    NIX_LDFLAGS="$(pkg-config --libs sqlite3) -L${zran}/lib -lzran -lzran_file_util $NIX_LDFLAGS"
  '';
}
  
