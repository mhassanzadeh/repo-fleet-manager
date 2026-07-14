PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
BASH_COMPLETION_DIR ?= $(HOME)/.local/share/bash-completion/completions
FISH_COMPLETION_DIR ?= $(HOME)/.config/fish/completions
CONFIG ?= configs/repo-fleet.example.json
ROOT ?= .
ARCHIVE ?=
BACKUP_OUTPUT ?=
CACHE_OUTPUT ?=
CACHE_DIR ?=
CACHE_ENGINE ?=
CACHE_IMAGE ?=
PROFILE ?=
GROUP ?=
PROJECT_NAME ?= demo-platform
PROJECT_DIR ?= $(PROJECT_NAME)
REPO_NAME ?=
REPO_PATH ?=
REPO_KIND ?= module
TEMPLATE ?= generic
LOCK_FILE ?= repo-fleet.lock.json
RUNTIME_SERVICE ?=
RUNTIME_TIMEOUT ?=
RUNTIME_INTERVAL ?=
RUNTIME_TAIL ?=
RUNTIME_ARGS = $(if $(RUNTIME_SERVICE),--service "$(RUNTIME_SERVICE)",) $(if $(RUNTIME_TIMEOUT),--timeout "$(RUNTIME_TIMEOUT)",) $(if $(RUNTIME_INTERVAL),--interval "$(RUNTIME_INTERVAL)",) $(if $(RUNTIME_TAIL),--tail "$(RUNTIME_TAIL)",)
WIZARD_OUTPUT ?= repo-fleet.json
WIZARD_SCAN ?= .
WIZARD_ANSWERS ?=
WIZARD_SESSION ?= .repo-fleet/wizard/session.json
SELECTION_ARGS = $(if $(PROFILE),--profile "$(PROFILE)",) $(if $(GROUP),--group "$(GROUP)",)

.PHONY: install install-cli install-editable install-completions install-all uninstall uninstall-completions doctor auth-status config-validate config-migrate graph safety-status ops-list test validate validate-docs completion-bash completion-fish local-plan local-localize local-localize-apply local-bootstrap local-bootstrap-apply local-remotes local-remotes-apply local-remotes-update publish-github publish-gitlab catalog-summary catalog-tree catalog-gaps catalog-docs catalog-check release-check release-artifacts build clean local-backup local-backup-apply local-backups local-backup-verify local-restore local-restore-apply config-render config-profiles config-groups init-project init-project-apply scaffold-templates scaffold-repository scaffold-repository-apply bootstrap-lock bootstrap-lock-apply bootstrap-verify cache-export cache-export-apply cache-list cache-verify cache-import cache-import-apply cache-bootstrap cache-bootstrap-apply config-wizard config-wizard-apply config-wizard-scan config-wizard-scan-apply config-wizard-answers config-wizard-reset runtime-status runtime-doctor runtime-wait runtime-up runtime-up-apply

install: install-cli install-completions

install-all: install

install-cli:
	$(PIP) install --user .

install-editable:
	$(PIP) install --user -e .

install-completions:
	install -d "$(BASH_COMPLETION_DIR)" "$(FISH_COMPLETION_DIR)"
	./scripts/rfm.sh completion bash > "$(BASH_COMPLETION_DIR)/rfm"
	./scripts/rfm.sh completion fish > "$(FISH_COMPLETION_DIR)/rfm.fish"
	@echo "Installed Bash completion: $(BASH_COMPLETION_DIR)/rfm"
	@echo "Installed Fish completion: $(FISH_COMPLETION_DIR)/rfm.fish"

uninstall:
	$(PIP) uninstall -y repo-fleet-manager

uninstall-completions:
	rm -f "$(BASH_COMPLETION_DIR)/rfm" "$(FISH_COMPLETION_DIR)/rfm.fish"

completion-bash:
	./scripts/rfm.sh completion bash

completion-fish:
	./scripts/rfm.sh completion fish

init-project:
	./scripts/rfm.sh init-project "$(PROJECT_NAME)" --directory "$(PROJECT_DIR)"

init-project-apply:
	./scripts/rfm.sh init-project "$(PROJECT_NAME)" --directory "$(PROJECT_DIR)" --apply

scaffold-templates:
	./scripts/rfm.sh scaffold templates

scaffold-repository:
	@test -n "$(REPO_NAME)" || (echo "REPO_NAME is required" >&2; exit 2)
	@test -n "$(REPO_PATH)" || (echo "REPO_PATH is required" >&2; exit 2)
	./scripts/rfm.sh scaffold repository "$(REPO_NAME)" --config "$(CONFIG)" --root "$(ROOT)" --path "$(REPO_PATH)" --kind "$(REPO_KIND)" --template "$(TEMPLATE)"

scaffold-repository-apply:
	@test -n "$(REPO_NAME)" || (echo "REPO_NAME is required" >&2; exit 2)
	@test -n "$(REPO_PATH)" || (echo "REPO_PATH is required" >&2; exit 2)
	./scripts/rfm.sh scaffold repository "$(REPO_NAME)" --config "$(CONFIG)" --root "$(ROOT)" --path "$(REPO_PATH)" --kind "$(REPO_KIND)" --template "$(TEMPLATE)" --apply

bootstrap-lock:
	./scripts/rfm.sh bootstrap --config "$(CONFIG)" --root "$(ROOT)" lock --output "$(LOCK_FILE)"

bootstrap-lock-apply:
	./scripts/rfm.sh bootstrap --config "$(CONFIG)" --root "$(ROOT)" lock --output "$(LOCK_FILE)" --apply

bootstrap-verify:
	./scripts/rfm.sh bootstrap --config "$(CONFIG)" --root "$(ROOT)" verify --lock-file "$(LOCK_FILE)"

local-plan:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) plan

local-remotes:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) remotes

local-remotes-apply:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) remotes --apply --seed

local-remotes-update:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) remotes --apply --update-mirrors

local-localize:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) localize

local-localize-apply:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) localize --apply

local-bootstrap:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) bootstrap

local-bootstrap-apply:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) bootstrap --apply --set-origin

local-backup:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) backup $(if $(BACKUP_OUTPUT),--output "$(BACKUP_OUTPUT)",)

local-backup-apply:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) backup $(if $(BACKUP_OUTPUT),--output "$(BACKUP_OUTPUT)",) --apply

local-backups:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) backups

local-backup-verify:
	@test -n "$(ARCHIVE)" || (echo "ARCHIVE is required" >&2; exit 2)
	./scripts/rfm.sh local verify-backup "$(ARCHIVE)"

local-restore:
	@test -n "$(ARCHIVE)" || (echo "ARCHIVE is required" >&2; exit 2)
	./scripts/rfm.sh local --root "$(ROOT)" $(SELECTION_ARGS) restore "$(ARCHIVE)"

local-restore-apply:
	@test -n "$(ARCHIVE)" || (echo "ARCHIVE is required" >&2; exit 2)
	./scripts/rfm.sh local --root "$(ROOT)" $(SELECTION_ARGS) restore "$(ARCHIVE)" --apply

cache-export:
	./scripts/rfm.sh cache --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) export $(if $(CACHE_OUTPUT),--output "$(CACHE_OUTPUT)",) $(if $(CACHE_DIR),--cache-dir "$(CACHE_DIR)",) $(if $(CACHE_ENGINE),--engine "$(CACHE_ENGINE)",) $(if $(CACHE_IMAGE),--image "$(CACHE_IMAGE)",)

cache-export-apply:
	./scripts/rfm.sh cache --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) export $(if $(CACHE_OUTPUT),--output "$(CACHE_OUTPUT)",) $(if $(CACHE_DIR),--cache-dir "$(CACHE_DIR)",) $(if $(CACHE_ENGINE),--engine "$(CACHE_ENGINE)",) $(if $(CACHE_IMAGE),--image "$(CACHE_IMAGE)",) --apply

cache-list:
	./scripts/rfm.sh cache --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) list $(if $(CACHE_DIR),--cache-dir "$(CACHE_DIR)",)

cache-verify:
	@test -n "$(ARCHIVE)" || (echo "ARCHIVE is required" >&2; exit 2)
	./scripts/rfm.sh cache verify "$(ARCHIVE)" --require-complete

cache-import:
	@test -n "$(ARCHIVE)" || (echo "ARCHIVE is required" >&2; exit 2)
	./scripts/rfm.sh cache --root "$(ROOT)" import "$(ARCHIVE)" $(if $(CACHE_ENGINE),--engine "$(CACHE_ENGINE)",)

cache-import-apply:
	@test -n "$(ARCHIVE)" || (echo "ARCHIVE is required" >&2; exit 2)
	./scripts/rfm.sh cache --root "$(ROOT)" import "$(ARCHIVE)" $(if $(CACHE_ENGINE),--engine "$(CACHE_ENGINE)",) --apply

cache-bootstrap:
	@test -n "$(ARCHIVE)" || (echo "ARCHIVE is required" >&2; exit 2)
	./scripts/rfm.sh cache --root "$(ROOT)" bootstrap "$(ARCHIVE)" $(if $(CACHE_ENGINE),--engine "$(CACHE_ENGINE)",)

cache-bootstrap-apply:
	@test -n "$(ARCHIVE)" || (echo "ARCHIVE is required" >&2; exit 2)
	./scripts/rfm.sh cache --root "$(ROOT)" bootstrap "$(ARCHIVE)" $(if $(CACHE_ENGINE),--engine "$(CACHE_ENGINE)",) --apply

# RFM_RUNTIME_TARGETS_BEGIN
runtime-status:
	./scripts/rfm.sh runtime --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) status $(if $(RUNTIME_SERVICE),--service "$(RUNTIME_SERVICE)",)

runtime-doctor:
	./scripts/rfm.sh runtime --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) doctor $(if $(RUNTIME_SERVICE),--service "$(RUNTIME_SERVICE)",) $(if $(RUNTIME_TAIL),--tail "$(RUNTIME_TAIL)",) --logs

runtime-wait:
	./scripts/rfm.sh runtime --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) wait $(RUNTIME_ARGS) --logs

runtime-up:
	./scripts/rfm.sh runtime --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) up $(RUNTIME_ARGS)

runtime-up-apply:
	./scripts/rfm.sh runtime --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) up $(RUNTIME_ARGS) --apply
# RFM_RUNTIME_TARGETS_END

publish-github:
	./scripts/rfm.sh repos --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) publish --provider github --namespace "$(NAMESPACE)"

publish-gitlab:
	./scripts/rfm.sh repos --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) publish --provider gitlab --namespace "$(NAMESPACE)"

catalog-summary:
	./scripts/rfm.sh catalog --root "$(ROOT)" $(SELECTION_ARGS) --view summary

catalog-tree:
	./scripts/rfm.sh catalog --root "$(ROOT)" $(SELECTION_ARGS) --view tree

catalog-gaps:
	./scripts/rfm.sh catalog --root "$(ROOT)" $(SELECTION_ARGS) --view gaps

catalog-docs:
	./scripts/rfm.sh catalog --root "$(ROOT)" $(SELECTION_ARGS) --view all --format markdown --output docs/generated/rfm-service-catalog.md
	./scripts/rfm.sh catalog --root "$(ROOT)" $(SELECTION_ARGS) --view gaps --format markdown --output reports/gap-analysis.md

catalog-check:
	./scripts/rfm.sh catalog --root "$(ROOT)" $(SELECTION_ARGS) --view summary --check-evidence

doctor:
	./scripts/rfm.sh doctor --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS)

config-validate:
	./scripts/rfm.sh config --config "$(CONFIG)" $(SELECTION_ARGS) validate --strict

config-migrate:
	./scripts/rfm.sh config --config "$(CONFIG)" migrate

config-render:
	./scripts/rfm.sh config --config "$(CONFIG)" $(SELECTION_ARGS) render

config-profiles:
	./scripts/rfm.sh config --config "$(CONFIG)" profiles

config-groups:
	./scripts/rfm.sh config --config "$(CONFIG)" groups

# RFM_CONFIG_WIZARD_TARGETS_BEGIN
config-wizard:
	./scripts/rfm.sh config wizard --root "$(ROOT)" --output "$(WIZARD_OUTPUT)" --quick

config-wizard-apply:
	./scripts/rfm.sh config wizard --root "$(ROOT)" --output "$(WIZARD_OUTPUT)" --quick --apply

config-wizard-scan:
	./scripts/rfm.sh config wizard --root "$(ROOT)" --scan "$(WIZARD_SCAN)" --output "$(WIZARD_OUTPUT)" --non-interactive

config-wizard-scan-apply:
	./scripts/rfm.sh config wizard --root "$(ROOT)" --scan "$(WIZARD_SCAN)" --output "$(WIZARD_OUTPUT)" --non-interactive --apply

config-wizard-answers:
	@test -n "$(WIZARD_ANSWERS)" || (echo "WIZARD_ANSWERS is required" >&2; exit 2)
	./scripts/rfm.sh config wizard --root "$(ROOT)" --answers "$(WIZARD_ANSWERS)" --output "$(WIZARD_OUTPUT)" --non-interactive --apply

config-wizard-reset:
	./scripts/rfm.sh config wizard --root "$(ROOT)" --session-file "$(WIZARD_SESSION)" --reset
# RFM_CONFIG_WIZARD_TARGETS_END

auth-status:
	./scripts/rfm.sh auth --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) status

graph:
	./scripts/rfm.sh graph --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) show

safety-status:
	./scripts/rfm.sh safety --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) status

ops-list:
	./scripts/rfm.sh ops --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) list

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests

validate-docs:
	./scripts/rfm.sh docs --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) validate-links

validate: config-validate release-check test validate-docs catalog-check

release-check:
	$(PYTHON) scripts/check_release_version.py

release-artifacts: validate clean build
	cd dist && sha256sum * > SHA256SUMS

build:
	@mkdir -p dist
	@if ! $(PYTHON) -m build --version >/dev/null 2>&1; then \
		echo "python-build is required for wheel and source distribution artifacts." >&2; \
		echo "Install it with: $(PIP) install build" >&2; \
		exit 2; \
	fi
	$(PYTHON) -m build

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
