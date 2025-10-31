# LevelDB Database Files

This directory contains LevelDB database files for FastBusiness field definitions.

## Structure

```
database/
├── Dir/          # Field definitions for DIR files
├── Filter/       # Field definitions for FILTER files
├── GridView/     # Field definitions for GRID VIEW files
└── GridInput/    # Field definitions for GRID INPUT files
```

## Usage

These folders will contain LevelDB data files (`.sst`, `.log`, `CURRENT`, `LOCK`, `MANIFEST`, etc.) when populated with field definitions.

By default, the system will try to use the VS Code extension database if available:
- Path: `C:\Users\nguye\.vscode\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database`

You can override this by setting the `FASTBUSINESS_VSCODE_DB_PATH` environment variable or by placing LevelDB files directly in these folders.

## Notes

- These folders are intentionally empty in the repository
- LevelDB files are binary and should not be committed to git
- The MCP server will automatically detect and use available databases
