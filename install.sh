#!/usr/bin/env bash
set -e

# hap one-line installer

BIN_DIR="$HOME/.local/bin"
REPO_RAW_URL="https://raw.githubusercontent.com/thefurdui/hap/refs/heads/main/bin/hap"

echo "=> Installing hap..."
mkdir -p "$BIN_DIR"

if curl -sL "$REPO_RAW_URL" -o "$BIN_DIR/hap"; then
  chmod +x "$BIN_DIR/hap"
  echo "=> Successfully installed to $BIN_DIR/hap"
else
  echo "=> Error: Failed to download hap."
  exit 1
fi

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "=> WARNING: $BIN_DIR is not in your PATH."
  echo "=> Add 'export PATH=\"\$HOME/.local/bin:\$PATH\"' to your .bashrc or .zshrc"
fi
