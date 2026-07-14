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
OUTPUT_FORMAT ?= text
LOG_DIR ?=
RUN_ID ?=
RETENTION_DAYS ?= 30
SUPPLY_SERVICE ?=
SUPPLY_ENGINE ?=
SUPPLY_OUTPUT_DIR ?=
SUPPLY_FORMAT ?= cyclonedx-json
SUPPLY_FAIL_ON ?= high
SUPPLY_KEY ?=
SUPPLY_CERTIFICATE_IDENTITY ?=
SUPPLY_CERTIFICATE_OIDC_ISSUER ?=
SUPPLY_ATTESTATION_TYPE ?=
SUPPLY_ARGS = $(if $(SUPPLY_SERVICE),--service "$(SUPPLY_SERVICE)",) $(if $(SUPPLY_OUTPUT_DIR),--output-dir "$(SUPPLY_OUTPUT_DIR)",)
POLICY_RULE ?=
POLICY_REPOSITORY ?=
POLICY_FAIL_ON ?= error
POLICY_ARGS = $(if $(POLICY_RULE),--rule "$(POLICY_RULE)",) $(if $(POLICY_REPOSITORY),--repository "$(POLICY_REPOSITORY)",) --fail-on "$(POLICY_FAIL_ON)"
PLUGIN_KIND ?=
PLUGIN_NAME ?=
ARTIFACT_SOURCE ?=
ARTIFACT_URI ?=
ARTIFACT_DESTINATION ?=
PLUGIN_ARGS = $(if $(PLUGIN_KIND),--kind "$(PLUGIN_KIND)",)
OBSERVABILITY_ARGS = --format "$(OUTPUT_FORMAT)" $(if $(LOG_DIR),--log-dir "$(LOG_DIR)",)
SELECTION_ARGS = $(if $(PROFILE),--profile "$(PROFILE)",) $(if $(GROUP),--group "$(GROUP)",)

.PHONY: install install-cli install-editable install-completions install-all uninstall uninstall-completions doctor auth-status config-validate config-migrate config-render config-profiles config-groups graph safety-status ops-list test validate validate-docs completion-bash completion-fish local-plan local-localize local-localize-apply local-bootstrap local-bootstrap-apply local-remotes local-remotes-apply local-remotes-update local-backup local-backup-apply local-backups local-backup-verify local-restore local-restore-apply publish-github publish-gitlab catalog-summary catalog-tree catalog-gaps catalog-docs catalog-check release-check release-artifacts build clean init-project init-project-apply scaffold-templates scaffold-repository scaffold-repository-apply bootstrap-lock bootstrap-lock-apply bootstrap-verify cache-export cache-export-apply cache-list cache-verify cache-import cache-import-apply cache-bootstrap cache-bootstrap-apply config-wizard config-wizard-apply config-wizard-scan config-wizard-scan-apply config-wizard-answers config-wizard-reset runtime-status runtime-doctor runtime-wait runtime-up runtime-up-apply logs-list logs-show logs-verify logs-purge logs-purge-apply supply-chain-resolve supply-chain-resolve-apply supply-chain-sbom supply-chain-sbom-apply supply-chain-scan supply-chain-scan-apply supply-chain-verify supply-chain-report supply-chain-collect supply-chain-collect-apply policy-check policy-enforce policy-explain policy-exceptions plugins-list plugins-doctor plugins-show artifacts-list artifacts-put artifacts-put-apply artifacts-get artifacts-get-apply artifacts-delete artifacts-delete-apply

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

# RFM_SUPPLY_CHAIN_TARGETS_BEGIN
supply-chain-resolve:
	./scripts/rfm.sh supply-chain --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) resolve $(SUPPLY_ARGS) $(if $(SUPPLY_ENGINE),--engine "$(SUPPLY_ENGINE)",)

supply-chain-resolve-apply:
	./scripts/rfm.sh supply-chain --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) resolve $(SUPPLY_ARGS) $(if $(SUPPLY_ENGINE),--engine "$(SUPPLY_ENGINE)",) --apply

supply-chain-sbom:
	./scripts/rfm.sh supply-chain --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) sbom $(SUPPLY_ARGS) --format "$(SUPPLY_FORMAT)"

supply-chain-sbom-apply:
	./scripts/rfm.sh supply-chain --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) sbom $(SUPPLY_ARGS) --format "$(SUPPLY_FORMAT)" --apply

supply-chain-scan:
	./scripts/rfm.sh supply-chain --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) scan $(SUPPLY_ARGS) --fail-on "$(SUPPLY_FAIL_ON)"

supply-chain-scan-apply:
	./scripts/rfm.sh supply-chain --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) scan $(SUPPLY_ARGS) --fail-on "$(SUPPLY_FAIL_ON)" --apply

supply-chain-verify:
	./scripts/rfm.sh supply-chain --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) verify $(SUPPLY_ARGS) --fail-on "$(SUPPLY_FAIL_ON)" $(if $(SUPPLY_KEY),--key "$(SUPPLY_KEY)",) $(if $(SUPPLY_CERTIFICATE_IDENTITY),--certificate-identity "$(SUPPLY_CERTIFICATE_IDENTITY)",) $(if $(SUPPLY_CERTIFICATE_OIDC_ISSUER),--certificate-oidc-issuer "$(SUPPLY_CERTIFICATE_OIDC_ISSUER)",) $(if $(SUPPLY_ATTESTATION_TYPE),--attestation-type "$(SUPPLY_ATTESTATION_TYPE)",)

supply-chain-report:
	./scripts/rfm.sh supply-chain --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) report $(SUPPLY_ARGS)

supply-chain-collect:
	./scripts/rfm.sh supply-chain --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) collect $(SUPPLY_ARGS) $(if $(SUPPLY_ENGINE),--engine "$(SUPPLY_ENGINE)",) --format "$(SUPPLY_FORMAT)" --fail-on "$(SUPPLY_FAIL_ON)"

supply-chain-collect-apply:
	./scripts/rfm.sh supply-chain --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) collect $(SUPPLY_ARGS) $(if $(SUPPLY_ENGINE),--engine "$(SUPPLY_ENGINE)",) --format "$(SUPPLY_FORMAT)" --fail-on "$(SUPPLY_FAIL_ON)" --apply
# RFM_SUPPLY_CHAIN_TARGETS_END

# RFM_OBSERVABILITY_TARGETS_BEGIN
# RFM_POLICY_TARGETS_BEGIN
policy-check:
	./scripts/rfm.sh policy --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) check $(POLICY_ARGS)

policy-enforce:
	./scripts/rfm.sh policy --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) enforce $(POLICY_ARGS)

policy-explain:
	@test -n "$(POLICY_RULE)" || (echo "POLICY_RULE is required" >&2; exit 2)
	./scripts/rfm.sh policy --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) explain "$(POLICY_RULE)"

policy-exceptions:
	./scripts/rfm.sh policy --config "$(CONFIG)" --root "$(ROOT)" $(SELECTION_ARGS) exceptions
# RFM_POLICY_TARGETS_END

logs-list:
	./scripts/rfm.sh logs --config "$(CONFIG)" --root "$(ROOT)" $(OBSERVABILITY_ARGS) list

logs-show:
	@test -n "$(RUN_ID)" || (echo "RUN_ID is required" >&2; exit 2)
	./scripts/rfm.sh logs --config "$(CONFIG)" --root "$(ROOT)" $(OBSERVABILITY_ARGS) show "$(RUN_ID)"

logs-verify:
	@test -n "$(RUN_ID)" || (echo "RUN_ID is required" >&2; exit 2)
	./scripts/rfm.sh logs --config "$(CONFIG)" --root "$(ROOT)" $(OBSERVABILITY_ARGS) verify "$(RUN_ID)"

logs-purge:
	./scripts/rfm.sh logs --config "$(CONFIG)" --root "$(ROOT)" $(OBSERVABILITY_ARGS) purge --retention-days "$(RETENTION_DAYS)"

logs-purge-apply:
	./scripts/rfm.sh logs --config "$(CONFIG)" --root "$(ROOT)" $(OBSERVABILITY_ARGS) purge --retention-days "$(RETENTION_DAYS)" --apply
# RFM_OBSERVABILITY_TARGETS_END


# RFM_PLUGIN_TARGETS_BEGIN
plugins-list:
	./scripts/rfm.sh $(OBSERVABILITY_ARGS) plugins --config "$(CONFIG)" --root "$(ROOT)" list $(PLUGIN_ARGS) --load

plugins-doctor:
	./scripts/rfm.sh $(OBSERVABILITY_ARGS) plugins --config "$(CONFIG)" --root "$(ROOT)" doctor

plugins-show:
	@test -n "$(PLUGIN_NAME)" || (echo "PLUGIN_NAME is required" >&2; exit 2)
	./scripts/rfm.sh $(OBSERVABILITY_ARGS) plugins --config "$(CONFIG)" --root "$(ROOT)" show "$(PLUGIN_NAME)" $(PLUGIN_ARGS)

artifacts-list:
	@test -n "$(ARTIFACT_URI)" || (echo "ARTIFACT_URI is required" >&2; exit 2)
	./scripts/rfm.sh $(OBSERVABILITY_ARGS) artifacts --config "$(CONFIG)" --root "$(ROOT)" list "$(ARTIFACT_URI)"

artifacts-put:
	@test -n "$(ARTIFACT_SOURCE)" || (echo "ARTIFACT_SOURCE is required" >&2; exit 2)
	@test -n "$(ARTIFACT_URI)" || (echo "ARTIFACT_URI is required" >&2; exit 2)
	./scripts/rfm.sh $(OBSERVABILITY_ARGS) artifacts --config "$(CONFIG)" --root "$(ROOT)" put "$(ARTIFACT_SOURCE)" "$(ARTIFACT_URI)"

artifacts-put-apply:
	@test -n "$(ARTIFACT_SOURCE)" || (echo "ARTIFACT_SOURCE is required" >&2; exit 2)
	@test -n "$(ARTIFACT_URI)" || (echo "ARTIFACT_URI is required" >&2; exit 2)
	./scripts/rfm.sh $(OBSERVABILITY_ARGS) artifacts --config "$(CONFIG)" --root "$(ROOT)" put "$(ARTIFACT_SOURCE)" "$(ARTIFACT_URI)" --apply

artifacts-get:
	@test -n "$(ARTIFACT_URI)" || (echo "ARTIFACT_URI is required" >&2; exit 2)
	@test -n "$(ARTIFACT_DESTINATION)" || (echo "ARTIFACT_DESTINATION is required" >&2; exit 2)
	./scripts/rfm.sh $(OBSERVABILITY_ARGS) artifacts --config "$(CONFIG)" --root "$(ROOT)" get "$(ARTIFACT_URI)" "$(ARTIFACT_DESTINATION)"

artifacts-get-apply:
	@test -n "$(ARTIFACT_URI)" || (echo "ARTIFACT_URI is required" >&2; exit 2)
	@test -n "$(ARTIFACT_DESTINATION)" || (echo "ARTIFACT_DESTINATION is required" >&2; exit 2)
	./scripts/rfm.sh $(OBSERVABILITY_ARGS) artifacts --config "$(CONFIG)" --root "$(ROOT)" get "$(ARTIFACT_URI)" "$(ARTIFACT_DESTINATION)" --apply

artifacts-delete:
	@test -n "$(ARTIFACT_URI)" || (echo "ARTIFACT_URI is required" >&2; exit 2)
	./scripts/rfm.sh $(OBSERVABILITY_ARGS) artifacts --config "$(CONFIG)" --root "$(ROOT)" delete "$(ARTIFACT_URI)"

artifacts-delete-apply:
	@test -n "$(ARTIFACT_URI)" || (echo "ARTIFACT_URI is required" >&2; exit 2)
	./scripts/rfm.sh $(OBSERVABILITY_ARGS) artifacts --config "$(CONFIG)" --root "$(ROOT)" delete "$(ARTIFACT_URI)" --apply
# RFM_PLUGIN_TARGETS_END

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
