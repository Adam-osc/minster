{ stdenv
, fetchFromGitHub
, pkg-config
, zlib
, python }:

stdenv.mkDerivation rec {
  pname = "zran";
  version = "5c9c398aa40a85cae1a75e7e9cb9e90d1d92de7f";

  src = fetchFromGitHub {
    owner = "pauldmccarthy";
    repo = "indexed_gzip";
    rev = version;
    hash = "sha256-jUiJJtfyG/5OOPPw3e2cyOV8m9MZo6IEtTSA6CIGgpI=";
  };

  buildInputs = [ zlib python ];
  nativeBuildInputs = [ pkg-config ];

  buildPhase = ''
    NIX_CFLAGS_COMPILE="$(pkg-config --cflags zlib python) $NIX_CFLAGS_COMPILE"
    NIX_LDFLAGS="$(pkg-config --libs zlib python) $NIX_LDFLAGS"
    gcc -shared -fPIC -I${src}/indexed_gzip -o libzran.so ${src}/indexed_gzip/zran.c
    gcc -shared -fPIC -I${src}/indexed_gzip -o libzran_file_util.so ${src}/indexed_gzip/zran_file_util.c
  '';

  installPhase = ''
    mkdir -p $out/lib $out/include
    cp libzran*.so $out/lib/
    cp ${src}/indexed_gzip/zran*.h $out/include/
  '';
}
