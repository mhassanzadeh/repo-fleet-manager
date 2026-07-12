# Git commit guide for RFM v0.9.0

Run commands from the repository root on `master`.

## Commit 1 — scaffolding engine

```bash
cd ~/Projects/repo-fleet-manager

git add \
  src/repo_fleet_manager/scaffold.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/__init__.py \
  src/repo_fleet_manager/data/rfm.bash \
  src/repo_fleet_manager/data/rfm.fish \
  completions/rfm.bash \
  completions/rfm.fish \
  tests/test_scaffold_bootstrap.py \
  tests/test_cli_completion.py \
  tests/test_release_metadata.py \
  Makefile \
  pyproject.toml \
  .github/workflows/release.yml \
  .github/ISSUE_TEMPLATE/bug_report.yml

git commit -m "feat(scaffold): add portable project and repository templates"
```

## Commit 2 — documentation and catalog

```bash
cd ~/Projects/repo-fleet-manager

git add \
  README.md \
  CHANGELOG.md \
  PATCH_NOTES_v0.9.0.md \
  GIT_COMMIT_GUIDE_v0.9.0.md \
  docs/14-project-scaffolding-and-bootstrap-lock.md \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  catalog/rfm-service-catalog.json \
  src/repo_fleet_manager/data/rfm-service-catalog.json

git commit -m "docs(scaffold): document portable bootstrap contracts"
```

## Validate and publish

```bash
cd ~/Projects/repo-fleet-manager

make validate
python3 scripts/check_release_version.py 0.9.0
git push origin master
```

After CI succeeds:

```bash
cd ~/Projects/repo-fleet-manager

git tag -a v0.9.0 -m "Repo Fleet Manager v0.9.0"
git push origin v0.9.0
```
