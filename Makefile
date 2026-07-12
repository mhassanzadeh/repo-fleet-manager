PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
BASH_COMPLETION_DIR ?= $(HOME)/.local/share/bash-completion/completions
FISH_COMPLETION_DIR ?= $(HOME)/.config/fish/completions

.PHONY: install install-cli install-editable install-completions install-all uninstall uninstall-completions doctor test validate-docs completion-bash completion-fish build clean

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
