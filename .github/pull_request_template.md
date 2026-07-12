## Summary

Describe the change and the operational problem it solves.

## Scope

- [ ] CLI or configuration
- [ ] Repository lifecycle/provider integration
- [ ] Local-only workflow
- [ ] Safety/recovery
- [ ] Packaging/release
- [ ] Documentation only

## Validation

```bash
make validate
python scripts/check_release_version.py
```

List any additional commands and results:

## Safety and compatibility

- [ ] State-changing commands remain dry-run by default.
- [ ] `--apply` behavior is covered by tests or executable validation.
- [ ] No credentials, tokens or private repository URLs are included.
- [ ] Config schema or migration documentation is updated when needed.
- [ ] Bash and Fish completion are updated when CLI syntax changes.
- [ ] Documentation and service catalog evidence are updated when capability status changes.
