# fingerprint سورس و مقایسه Docker image

## هدف

در پروژه‌های چندسرویسی، یک مشکل رایج این است که container در حال اجرا با سورس فعلی workspace یکی نیست. Repo Fleet Manager برای هر سرویس digest سورس تولید می‌کند و آن را به Docker Compose به‌صورت build arg، environment و label تزریق می‌کند.

## محاسبه digest

```bash
rfm source fingerprint
rfm source fingerprint --write
```

خروجی `--write`:

```text
.repo-fleet/build/
├── metadata.json
├── build.env
├── compose.env
└── docker-compose.source-metadata.yml
```

## قواعد پیش‌فرض fingerprint

فایل‌های داخل مسیرهای زیر در digest لحاظ می‌شوند:

- `src`
- `tests`
- `openapi`
- `docs`
- `app`
- `lib`
- `cmd`
- `internal`
- `pkg`
- `public`

و فایل‌های ریشه مثل `Dockerfile`, `pyproject.toml`, `package.json`, `go.mod`, `README.md` هم لحاظ می‌شوند.

مسیرهایی مثل `.git`, `node_modules`, `build`, `dist`, `.venv`, `target` حذف می‌شوند.

## اجرای compose با metadata

```bash
rfm source fingerprint --write
rfm compose up --apply -- -d --build --force-recreate
```

## verify imageها

```bash
rfm images verify
rfm images verify --json
```

اگر digest image با digest سورس فعلی یکی نباشد، یعنی image باید rebuild شود یا container از image قدیمی اجرا شده است.

## پیش‌نیاز در Dockerfile/Compose

Compose override تولیدشده labelهای زیر را به سرویس اضافه می‌کند:

```yaml
labels:
  io.repo-fleet.service: api
  io.repo-fleet.source-digest: ${MYAPP_API_BUILD_SOURCE_DIGEST}
```

برای اینکه label روی image ساخته‌شده هم ثبت شود، Dockerfile یا Compose build باید build args را بپذیرد. نمونه:

```dockerfile
ARG MYAPP_BUILD_SHA=unknown
ARG MYAPP_BUILD_SOURCE_DIGEST=unknown
ARG MYAPP_BUILD_TIME=unknown

LABEL io.repo-fleet.build-sha=$MYAPP_BUILD_SHA
LABEL io.repo-fleet.source-digest=$MYAPP_BUILD_SOURCE_DIGEST
LABEL io.repo-fleet.build-time=$MYAPP_BUILD_TIME
```

## Immutable provenance

فرمان قدیمی `rfm images verify` labelهای image محلی را بررسی می‌کند. برای زنجیره کامل registry digest، SBOM، vulnerability و Cosign از `rfm supply-chain` استفاده کنید. verification جدید fingerprint فعلی را با `io.repo-fleet.source-digest` مقایسه و سپس فقط reference ثابت digest را می‌پذیرد.
