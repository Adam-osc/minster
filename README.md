# Minster
- x86_64-linux, aarch64-linux, x86_64-darwin, aarch64-darwin are the only supported architectures.
- The program was tested only on aarch64-linux (refer to [jetson-nanopore-nixos-config](https://github.com/Adam-osc/jetson-nanopore-nixos-config)) and aarch64-darwin.

**Nix Installation**  
- Ensure that [Nix](https://nixos.org/download.html) is installed on your system. 
- Enable nix-command and flakes experimental features for your installtion or run Nix commands in this README with `--experimental-features 'nix-command flakes'`.

**Runtime dependencies**  
- The MinKNOW and Dorado server must be up and running.
- The current user must have read and write access to the Dorado server socket, and read-write-execute access to the target experiment's data directory.
  - Read access to the experiment's data directory is required because pyfastx writes its index files in the same location as the FASTQ file being read.

**Version Compatibility**
- The versions of minknow-api and ont-pybasecall-client-lib python packages supplied in this flake were tested to work with MinKNOW Core version 6.2.8 and Dorado server version 7.6.8.
- When running a different version of Minknow Core or Dorado server modify the version of minknow-api and ont-pybasecall-client-lib in [flake.nix](./flake.nix). Ensure that the requested versions are provided by the relevant nix files. 

## Running the program
1. Enter a development shell with the necessary python dependencies using:
```bash
nix develop
```
- The development shell also includes the MinKNOW frontend Kingfisher; the packaged version can be only installed on x86_64-linux and aarch64-linux.
- It can be launched by running:
```bash
ont-kingfisher
```

2. Inside the development shell, the program can be launched with:
```bash
python main.py --config /path/to/config.toml
```
- An [example config](./example-ibf.toml) file with all the tweakable options in provided.

3. Start a sequencing experiment in MinKNOW with live basecalling.
- The read until client may fail to connect to the sequencer even if it is in the `acquisition running` state.
