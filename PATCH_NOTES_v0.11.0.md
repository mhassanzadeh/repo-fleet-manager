# Repo Fleet Manager v0.11.0 patch notes

## Release identity

- Base revision: `fa77a805e53baca77ebed0de82edd303f9b01006`
- Base version: `0.10.0`
- Target version: `0.11.0`
- Schema version: `1.0.0` unchanged
- Scope: GAP-018 — Interactive Configuration Wizard

## Added

- `rfm config wizard`
- quick and advanced interactive modes
- Git/submodule/Compose/image scan
- JSON answer files and non-interactive generation
- resumable session and reset
- dry-run, diff, atomic write and backup
- Bash/Fish completion and Make targets

## Safety

- secret-like answers are rejected
- generated paths must be portable and relative
- config is strictly validated before replacement
- existing configs receive backups by default
