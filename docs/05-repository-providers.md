# GitHub and GitLab providers

RFM separates the provider key from its `driver`. This permits multiple accounts or hosts such as `github-personal`, `github-work` and `gitlab-customer`.

## GitHub

```json
"github-work": {
  "type": "remote",
  "driver": "github",
  "namespace": "my-org",
  "host": "github.com",
  "cli": "gh",
  "profile": "work",
  "user": "my-user",
  "required_scopes": [],
  "url_template": "git@github.com:{namespace}/{repo}.git"
}
```

## GitLab

```json
"gitlab-work": {
  "type": "remote",
  "driver": "gitlab",
  "namespace": "my-group",
  "host": "gitlab.com",
  "cli": "glab",
  "profile": "work",
  "user": "my-user",
  "required_scopes": [],
  "url_template": "git@gitlab.com:{namespace}/{repo}.git"
}
```

## Authentication diagnostics

RFM does not store credentials or tokens in the manifest. Authenticate through `gh`, `glab`, CI variables or an external credential system, then inspect the active context:

```bash
rfm auth --config repo-fleet.json status
rfm auth --config repo-fleet.json status --provider github-work --verbose
rfm auth --config repo-fleet.json status --provider github-work --strict-scopes
rfm doctor --config repo-fleet.json --auth --strict-auth
```

The report shows the driver, host, expected/active user, token environment variable names, detected/required scopes and tested capabilities. Token values are never printed and known token patterns are redacted from CLI output.

Some token types do not expose scope metadata. Without `--strict-scopes`, RFM reports the scope state as unknown; with strict mode it rejects provider mutation when configured scopes cannot be verified.

## Create and publish

```bash
rfm repos --config repo-fleet.json create --provider github-work
rfm repos --config repo-fleet.json create --provider github-work --apply

rfm repos --config repo-fleet.json publish \
  --provider github-work \
  --namespace my-org \
  --remote-name personal \
  --apply
```

`publish` keeps the local `origin` intact by using a separate remote name unless configured otherwise.

## Native fork

A repository with `source_type: upstream`, `remote_mode: fork` and `fork_from`/`upstream_url` can be forked natively:

```bash
rfm repos --config repo-fleet.json fork --provider github-work
rfm repos --config repo-fleet.json fork --provider github-work --apply

rfm repos --config repo-fleet.json fork --provider gitlab-work --apply
```

RFM then adds or updates the configured personal remote in the local worktree. The original source remains available as upstream input to local mirroring and reconciliation.

## Mirror publication

For `remote_mode: mirror`, first materialize the local bare mirror and then publish all refs:

```bash
rfm local --config repo-fleet.json remotes --mirror-sources --apply
rfm repos --config repo-fleet.json mirror --provider gitlab-work --apply
```

A mirror push is intentionally explicit because it can delete destination refs that are absent from the local bare mirror.

## Reconciliation

```bash
rfm repos --config repo-fleet.json reconcile --provider github-work
rfm repos --config repo-fleet.json reconcile --provider github-work --apply
```

The report compares existence, fork relationship, fork parent, default branch, visibility and topics. Apply mode repairs supported metadata drift. Incorrect fork lineage remains a reported issue rather than being destructively recreated.

## Runtime override

```bash
rfm repos --config repo-fleet.json audit --provider gitlab-work --namespace another-group
rfm submodules --config repo-fleet.json sync --provider gitlab-work --namespace another-group
```

Provider-side `--apply` commands run an authentication preflight before changing state.
