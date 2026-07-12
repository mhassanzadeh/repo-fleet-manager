# Migration Guide

برای مهاجرت پروژه فعلی به Repo Fleet Manager:

1. پکیج را کنار پروژه اصلی clone یا extract کنید.
2. فایل نمونه را کپی کنید:

```bash
cp repo-fleet-manager/configs/goftaroo.example.json main-platform/repo-fleet.json
```

3. در پروژه اصلی:

```bash
cd main-platform
../repo-fleet-manager/scripts/rfm.sh doctor
../repo-fleet-manager/scripts/rfm.sh repos audit
```

4. برای sync ریموت‌ها ابتدا dry-run بگیرید:

```bash
../repo-fleet-manager/scripts/rfm.sh submodules sync --provider github --namespace <owner>
```

5. بعد از بازبینی خروجی:

```bash
../repo-fleet-manager/scripts/rfm.sh submodules sync --provider github --namespace <owner> --apply
```

6. fingerprint و compose metadata:

```bash
../repo-fleet-manager/scripts/rfm.sh source fingerprint --write
../repo-fleet-manager/scripts/rfm.sh compose up --apply -- -d --build --force-recreate
../repo-fleet-manager/scripts/rfm.sh images verify
```
