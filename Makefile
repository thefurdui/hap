# Variables
PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin
DATADIR ?= $(HOME)/.local/share/hap
SCRIPT = bin/hap
TEMPLATE = templates/hap.kdl

# Default target
all:
	@echo "Run 'make install' to install hap to $(BINDIR)"

# Install target
install:
	@mkdir -p $(BINDIR)
	@mkdir -p $(DATADIR)/templates
	@install -m 755 $(SCRIPT) $(BINDIR)/hap
	@cp $(TEMPLATE) $(DATADIR)/templates/hap.kdl
	@echo "✅ Installed hap to $(BINDIR)/hap"

# Uninstall target
uninstall:
	@rm -f $(BINDIR)/hap
	@rm -rf $(DATADIR)/templates
	@echo "🗑️  Uninstalled hap"

.PHONY: all install uninstall
