# Git commit guide for RFM v0.8.0

RFM is currently a standalone repository without Git submodules. Run commands from the repository root on `master`.

## Commit 1 — profile and group engine

```bash
cd ~/Projects/repo-fleet-manager

git switch master
git pull --ff-only

git add \
  src/repo_fleet_manager/profiles.py \
  src/repo_fleet_manager/config.py \
  src/repo_fleet_manager/schema.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/__init__.py \
  schemas/repo-fleet.schema.json \
  src/repo_fleet_manager/data/repo-fleet.schema.json \
  configs/repo-fleet.example.json \
  completions \
  src/repo_fleet_manager/data/rfm.bash \
  src/repo_fleet_manager/data/rfm.fish \
  Makefile \
  pyproject.toml \
  tests/test_profiles_groups.py \
  tests/test_cli_completion.py \
  tests/test_release_metadata.py

git commit -m "feat(config): add profiles overlays and repository groups"
```

## Commit 2 — documentation and catalog

```bash
cd ~/Projects/repo-fleet-manager

git add \
  README.md \
  CHANGELOG.md \
  PATCH_NOTES_v0.8.0.md \
  GIT_COMMIT_GUIDE_v0.8.0.md \
  docs/02-configuration.md \
  docs/07-command-reference.md \
  docs/13-profiles-overlays-and-groups.md \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  catalog/rfm-service-catalog.json \
  src/repo_fleet_manager/data/rfm-service-catalog.json

git commit -m "docs(config): document profile and group workflows"
```

## Validate and publish

```bash
cd ~/Projects/repo-fleet-manager

make validate
python3 scripts/check_release_version.py 0.8.0

git push origin master
```

After CI succeeds:

```bash
cd ~/Projects/repo-fleet-manager

git tag -a v0.8.0 -m "Repo Fleet Manager v0.8.0"
git push origin v0.8.0
```
