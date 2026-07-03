#!/usr/bin/env bash
set -e

# hap one-line installer

BIN_DIR="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/hap/templates"

# Base URL for raw GitHub files
REPO_BASE_URL="https://raw.githubusercontent.com/thefurdui/hap/refs/heads/main/"

echo "=> Installing hap..."
mkdir -p "$BIN_DIR"
mkdir -p "$DATA_DIR"

# Download Executable
if curl -sL "$REPO_BASE_URL/bin/hap" -o "$BIN_DIR/hap"; then
  chmod +x "$BIN_DIR/hap"
  echo "=> Installed executable to $BIN_DIR/hap"
else
  echo "=> Error: Failed to download hap executable."
  exit 1
fi

# Download Base Template
if curl -sL "$REPO_BASE_URL/templates/hap.kdl" -o "$DATA_DIR/hap.kdl"; then
  echo "=> Installed template to $DATA_DIR/hap.kdl"
else
  echo "=> Error: Failed to download hap.kdl template."
  exit 1
fi

echo "=> hap installed successfully."

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "=> WARNING: $BIN_DIR is not in your PATH."
  echo "=> Add 'export PATH=\"\$HOME/.local/bin:\$PATH\"' to your .bashrc or .zshrc"
fi
