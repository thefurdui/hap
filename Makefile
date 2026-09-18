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

.PHONY: all install uninstall
