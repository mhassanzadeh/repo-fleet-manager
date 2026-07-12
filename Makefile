PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
BASH_COMPLETION_DIR ?= $(HOME)/.local/share/bash-completion/completions
FISH_COMPLETION_DIR ?= $(HOME)/.config/fish/completions
CONFIG ?= configs/repo-fleet.example.json
ROOT ?= .

.PHONY: install install-cli install-editable install-completions install-all uninstall uninstall-completions doctor test validate-docs completion-bash completion-fish local-plan local-localize local-localize-apply local-bootstrap local-bootstrap-apply local-remotes local-remotes-apply local-remotes-update publish-github publish-gitlab catalog-summary catalog-tree catalog-gaps catalog-docs catalog-check build clean

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
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" plan

local-remotes:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" remotes

local-remotes-apply:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" remotes --apply --seed

local-remotes-update:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" remotes --apply --update-mirrors

local-localize:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" localize

local-localize-apply:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" localize --apply

local-bootstrap:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" bootstrap

local-bootstrap-apply:
	./scripts/rfm.sh local --config "$(CONFIG)" --root "$(ROOT)" bootstrap --apply --set-origin

publish-github:
	./scripts/rfm.sh repos --config "$(CONFIG)" --root "$(ROOT)" publish --provider github --namespace "$(NAMESPACE)"

publish-gitlab:
	./scripts/rfm.sh repos --config "$(CONFIG)" --root "$(ROOT)" publish --provider gitlab --namespace "$(NAMESPACE)"

catalog-summary:
	./scripts/rfm.sh catalog --root "$(ROOT)" --view summary

catalog-tree:
	./scripts/rfm.sh catalog --root "$(ROOT)" --view tree

catalog-gaps:
	./scripts/rfm.sh catalog --root "$(ROOT)" --view gaps

catalog-docs:
	./scripts/rfm.sh catalog --root "$(ROOT)" --view all --format markdown --output docs/generated/rfm-service-catalog.md
	./scripts/rfm.sh catalog --root "$(ROOT)" --view gaps --format markdown --output reports/gap-analysis.md

catalog-check:
	./scripts/rfm.sh catalog --root "$(ROOT)" --view summary --check-evidence

doctor:
	./scripts/rfm.sh doctor --config configs/goftaroo.example.json

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests

validate-docs:
	./scripts/rfm.sh docs --config configs/goftaroo.example.json validate-links

build:
	$(PYTHON) -m build

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
