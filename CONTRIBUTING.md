# Contributing to Repo Fleet Manager

## Development setup

RFM requires Python 3.11 or newer.

```bash
git clone git@github.com:mhassanzadeh/repo-fleet-manager.git
cd repo-fleet-manager
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip build
python -m pip install -e .
make install-completions
```

## Before submitting a change

```bash
make validate
python scripts/check_release_version.py
bash -n completions/rfm.bash
```

When CLI syntax changes, update Bash and Fish completion. When config fields change, update the JSON Schema, migration logic, examples and documentation. When capability maturity changes, update both service catalog manifests and regenerate catalog documentation.

## Safety requirements

State-changing commands must remain dry-run by default. Real changes must require `--apply`. Bypassing safety checks must require both `--force` and a meaningful `--reason` recorded in the operation journal.

Tests must not depend on access to a contributor's real GitHub/GitLab account. Provider workflows should use mocks, temporary repositories or an explicitly isolated test namespace.

## Commit messages

Use Conventional Commit-style messages:

```text
feat(local): add offline repository bundle export
fix(publish): preserve an existing personal remote
docs(release): document checksum verification
```

Keep code/tests and documentation in separate commits when that improves reviewability.

## Pull requests

Describe the operational problem, configuration impact, rollback behavior and validation commands. Never include tokens, credentials, private repository URLs or unredacted authentication output.
