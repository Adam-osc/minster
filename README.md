# Minster

**Nix Installation**  
- Ensure that [Nix](https://nixos.org/download.html) is installed on your system. 
- Enable nix-command and flakes experimental features for your installtion or run Nix commands in this README with `--experimental-features 'nix-command flakes'`.

**Runtime dependencies**  
- The MinKNOW and Dorado server must be up and running.
- The current user must have read and write access to the Dorado server socket, and read and execute access to the target experiment's data directory.

**Version Compatibility**
- The versions of minknow-api and ont-pybasecall-client-lib python packages supplied in this flake were tested to work with MinKNOW Core version 6.2.8 and Dorado server version 7.2.8.

## Running the program
1. Enter a development shell with the necessary python dependencies using:
```bash
nix develop
```

2. Inside the development shell, the program can be launched with:
```bash
python main.py --config /path/to/config.toml
```
- An [example config](./example.toml) file with all the tweakable options in provided.

3. Start a sequencing experiment in MinKNOW with live basecalling.
