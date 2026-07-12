PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
BASH_COMPLETION_DIR ?= $(HOME)/.local/share/bash-completion/completions
FISH_COMPLETION_DIR ?= $(HOME)/.config/fish/completions
CONFIG ?= configs/repo-fleet.example.json
ROOT ?= .
ARCHIVE ?=
BACKUP_OUTPUT ?=
PROFILE ?=
GROUP ?=
SELECTION_ARGS = $(if $(PROFILE),--profile "$(PROFILE)",) $(if $(GROUP),--group "$(GROUP)",)

.PHONY: install install-cli install-editable install-completions install-all uninstall uninstall-completions doctor auth-status config-validate config-migrate graph safety-status ops-list test validate validate-docs completion-bash completion-fish local-plan local-localize local-localize-apply local-bootstrap local-bootstrap-apply local-remotes local-remotes-apply local-remotes-update publish-github publish-gitlab catalog-summary catalog-tree catalog-gaps catalog-docs catalog-check release-check release-artifacts build clean local-backup local-backup-apply local-backups local-backup-verify local-restore local-restore-apply config-render config-profiles config-groups

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
