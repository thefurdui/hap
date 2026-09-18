# Variables
PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin
XDG_DATA_HOME ?= $(HOME)/.local/share
DATADIR ?= $(XDG_DATA_HOME)/hap
SCRIPT = bin/hap
TEMPLATE = templates/hap.kdl

# Default target
all:
	@echo "Run 'make install' to install hap to $(BINDIR)"

# Install target
install:
	@test -n "$(BINDIR)" && test "$(BINDIR)" != / && test -n "$(DATADIR)" && test "$(DATADIR)" != /
	@mkdir -p "$(BINDIR)"
	@mkdir -p "$(DATADIR)/templates"
	@install -m 755 "$(SCRIPT)" "$(BINDIR)/hap"
	@install -m 644 "$(TEMPLATE)" "$(DATADIR)/templates/hap.kdl"
	@echo "✅ Installed hap to $(BINDIR)/hap"

# Uninstall target
uninstall:
	@test -n "$(BINDIR)" && test "$(BINDIR)" != / && test -n "$(DATADIR)" && test "$(DATADIR)" != /
	@rm -f "$(BINDIR)/hap" "$(DATADIR)/templates/hap.kdl"
	@rmdir "$(DATADIR)/templates" 2>/dev/null || true
	@echo "🗑️  Uninstalled hap"

test:
	python3 -m unittest discover -s tests -v

lint:
	bash -n bin/hap install.sh
	shellcheck bin/hap install.sh

release-prepare checksums:
	python3 scripts/release_checks.py --write

check-release:
	python3 scripts/release_checks.py

check-tag:
	python3 scripts/release_checks.py --tag "v$$(cat VERSION)"

check: lint check-release test

.PHONY: all install uninstall test lint release-prepare checksums check-release check-tag check
