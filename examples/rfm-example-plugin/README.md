# RFM example plugin

Reference implementations for all four Repo Fleet Manager v1 plugin kinds.

```bash
cd examples/rfm-example-plugin
python3 -m pip install -e .
rfm plugins doctor
rfm plugins list --load
rfm catalog --view summary --format csv
```

The provider and runtime examples are deliberately non-destructive. The artifact backend maps
`example://bucket/key` URIs into `.repo-fleet/example-artifacts/bucket/key` below the selected root.
