{ stdenv
, fetchFromGitHub
, pkg-config
, zlib
, python }:

let
  outputDynLib = if stdenv.hostPlatform.isLinux then "libzran.so" else "libzran.dylib";
  compilationCommand = src: (if stdenv.hostPlatform.isLinux then
                               "cc -shared -fPIC -I${src}/indexed_gzip -o libzran.so ${src}/indexed_gzip/zran.c ${src}/indexed_gzip/zran_file_util.c"
                             else
                               "cc -dynamiclib -fPIC -I${src}/indexed_gzip -install_name $out/lib/libzran.dylib -o libzran.dylib ${src}/indexed_gzip/zran.c ${src}/indexed_gzip/zran_file_util.c");

in
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
    NIX_LDFLAGS="$(pkg-config --libs zlib python) -lpython${python.pythonVersion} $NIX_LDFLAGS"
    ${(compilationCommand src)}
  '';
  installPhase = ''
    mkdir -p $out/lib $out/include
    cp ${outputDynLib} $out/lib/
    cp ${src}/indexed_gzip/zran*.h $out/include/
  '';
}
