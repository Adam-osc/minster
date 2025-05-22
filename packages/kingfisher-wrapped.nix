{ fetchurl, stdenv, dpkg, lib, appimageTools, buildFHSEnv, writeShellScript, commandLineArgs ? [] }:

let
  pname = "ont-kingfisher";
  version = "6.2.14";

  sources = {
    linux = fetchurl {
      url = "http://cdn.oxfordnanoportal.com/apt/pool/non-free/o/ont-kingfisher-ui-mk1c/ont-kingfisher-ui-mk1c_${version}-1~bionic_all.deb";
      sha256 = "sha256-oeTE/yXR5JEJtox1bV237u4PX7bkG+PmVh/xTdRVy6E=";
    };
  };

  unpackedONTKingfisher = stdenv.mkDerivation {
    inherit pname version;

    nativeBuildInputs = [  ];
    buildInputs = [ dpkg ];

    src = sources.linux;

    unpackPhase = ''
      runHook preUnpack

      dpkg-deb -x $src temp

      runHook postUnpack
    '';

    installPhase = ''
      runHook preInstall

      mkdir -p $out
      cp -r temp/opt $out/

      runHook postInstall
    '';
  };

  passthru = { };
  
  meta = with lib; {
    platforms = [ "x86_64-linux" "aarch64-linux" ];
    maintainers = with maintainers; [  ];
  };

  fhsEnvKingfisher =  buildFHSEnv (appimageTools.defaultFhsEnvArgs // {
    inherit pname version;

    targetPkgs = pkgs: [
      pkgs.gtk3.out
      unpackedONTKingfisher
    ];

    runScript = writeShellScript "kingfisher-wrapper.sh" ''
      exec ${unpackedONTKingfisher}"/opt/ont/ui/kingfisher/MinKNOW UI" ${ lib.strings.escapeShellArgs commandLineArgs } "$@"
    '';

    inherit meta passthru;
  });
in
fhsEnvKingfisher
