# Variables
PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin
SCRIPT = bin/hap

# Default target
all:
	@echo "Run 'make install' to install hap to $(BINDIR)"

# Install target
install:
	@mkdir -p $(BINDIR)
	@install -m 755 $(SCRIPT) $(BINDIR)/hap
	@echo "✅ Installed hap to $(BINDIR)/hap"

# Uninstall target
uninstall:
	@rm -f $(BINDIR)/hap
	@echo "🗑️  Uninstalled hap"

.PHONY: all install uninstall
