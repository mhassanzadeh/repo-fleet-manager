# Repo Fleet Manager v0.6.2

## Fixed

- Fixed `NameError: git_is_worktree is not defined` in `rfm repos publish`.
- Added a regression test covering dry-run publication of an existing standalone root repository.

## Upgrade

```bash
python3 -m pip install --user --upgrade .
# or
make install-editable
```
