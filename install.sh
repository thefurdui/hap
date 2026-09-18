#!/usr/bin/env bash
set -euo pipefail
((BASH_VERSINFO[0] >= 4)) || { printf 'Install Bash 4 or newer first\n' >&2; exit 1; }

# Select a release tag or an immutable commit. Never mix files from mutable main.
# Generated from VERSION by make release-prepare.
REF="${HAP_INSTALL_REF:-v1.2.1}"
[[ "$REF" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ || "$REF" =~ ^[0-9a-f]{40}$ ]] || {
  printf 'Invalid HAP_INSTALL_REF: %s\n' "$REF" >&2; exit 1;
}
BIN_DIR="${HAP_BIN_DIR:-$HOME/.local/bin}"
DATA_DIR="${HAP_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/hap}"
BASE_URL="https://raw.githubusercontent.com/thefurdui/hap/$REF"
for dependency in curl bash install mktemp; do
  command -v "$dependency" >/dev/null || { printf 'Missing dependency: %s\n' "$dependency" >&2; exit 1; }
done
if command -v sha256sum >/dev/null; then
  checksum() { sha256sum < "$1"; }
elif command -v shasum >/dev/null; then
  checksum() { shasum -a 256 < "$1"; }
else
  printf 'sha256sum or shasum is required\n' >&2; exit 1
fi

staging=$(mktemp -d)
exe_tmp=""; layout_tmp=""; lock=""; exe_changed=false; layout_changed=false; complete=false
cleanup() {
  local status=$?
  trap - EXIT
  if [[ "$complete" != true ]]; then
    if [[ "$exe_changed" == true ]]; then
      if [[ -f "$staging/old-hap" ]]; then
        cp -p "$staging/old-hap" "$exe_tmp"
        mv -f "$exe_tmp" "$BIN_DIR/hap"
      else
        rm -f "$BIN_DIR/hap"
      fi
    fi
    if [[ "$layout_changed" == true ]]; then
      if [[ -f "$staging/old-layout" ]]; then
        cp -p "$staging/old-layout" "$layout_tmp"
        mv -f "$layout_tmp" "$DATA_DIR/templates/hap.kdl"
      else
        rm -f "$DATA_DIR/templates/hap.kdl"
      fi
    fi
  fi
  [[ -z "$exe_tmp" ]] || rm -f "$exe_tmp"
  [[ -z "$layout_tmp" ]] || rm -f "$layout_tmp"
  [[ -z "$lock" ]] || rmdir "$lock"
  rm -rf "$staging"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "$staging/bin" "$staging/templates"
for file in bin/hap templates/hap.kdl SHA256SUMS; do
  curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' \
    --output "$staging/$file" "$BASE_URL/$file"
done

verified=0
while read -r expected file extra; do
  [[ "$expected" =~ ^[0-9a-f]{64}$ && -z "${extra:-}" ]] || { printf 'Invalid checksum manifest\n' >&2; exit 1; }
  case "$file" in bin/hap|templates/hap.kdl) ;; *) printf 'Unexpected manifest entry\n' >&2; exit 1 ;; esac
  actual=$(checksum "$staging/$file")
  [[ "${actual%% *}" == "$expected" ]] || { printf 'Checksum mismatch: %s\n' "$file" >&2; exit 1; }
  case "$file" in bin/hap) [[ ! -e "$staging/verified-exe" ]]; touch "$staging/verified-exe" ;; templates/hap.kdl) [[ ! -e "$staging/verified-layout" ]]; touch "$staging/verified-layout" ;; esac
  verified=$((verified + 1))
done < "$staging/SHA256SUMS"
[[ $verified -eq 2 && -f "$staging/verified-exe" && -f "$staging/verified-layout" ]] || { printf 'Incomplete checksum manifest\n' >&2; exit 1; }
bash -n "$staging/bin/hap"

mkdir -p "$BIN_DIR" "$DATA_DIR/templates"
mkdir "$BIN_DIR/.hap-install.lock" || { printf 'Another installation is active\n' >&2; exit 1; }
lock="$BIN_DIR/.hap-install.lock"
for target in "$BIN_DIR/hap" "$DATA_DIR/templates/hap.kdl"; do
  [[ ! -L "$target" && ( ! -e "$target" || -f "$target" ) ]] || { printf 'Unsafe install target: %s\n' "$target" >&2; exit 1; }
done
[[ ! -f "$BIN_DIR/hap" ]] || cp -p "$BIN_DIR/hap" "$staging/old-hap"
[[ ! -f "$DATA_DIR/templates/hap.kdl" ]] || cp -p "$DATA_DIR/templates/hap.kdl" "$staging/old-layout"
exe_tmp=$(mktemp "$BIN_DIR/.hap.XXXXXXXX")
layout_tmp=$(mktemp "$DATA_DIR/templates/.hap.XXXXXXXX")
install -m 755 "$staging/bin/hap" "$exe_tmp"
install -m 644 "$staging/templates/hap.kdl" "$layout_tmp"
exe_changed=true
mv -f "$exe_tmp" "$BIN_DIR/hap"
layout_changed=true
mv -f "$layout_tmp" "$DATA_DIR/templates/hap.kdl"
complete=true
printf 'Installed hap %s to %s/hap\n' "$REF" "$BIN_DIR"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  printf 'Add %s to PATH.\n' "$BIN_DIR"
fi
