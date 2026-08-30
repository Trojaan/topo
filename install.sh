#!/usr/bin/env bash
set -euo pipefail

REPO="Trojaan/topo"
INSTALL_DIR="${TOPO_INSTALL_DIR:-$HOME/.topo/bin}"
REQUESTED_VERSION="${TOPO_VERSION:-}"

fail() {
  echo "error: $1" >&2
  exit 1
}

command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v unzip >/dev/null 2>&1 || fail "unzip is required"

case "$(uname -s)" in
  Darwin) platform="macos" ;;
  Linux) platform="linux" ;;
  *) fail "unsupported operating system: $(uname -s)" ;;
esac

case "$(uname -m)" in
  x86_64|amd64) architecture="amd64" ;;
  arm64|aarch64) architecture="arm64" ;;
  *) fail "unsupported architecture: $(uname -m)" ;;
esac

if [[ -n "$REQUESTED_VERSION" ]]; then
  version="$REQUESTED_VERSION"
else
  version="$(
    curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" |
      sed -nE 's/.*"tag_name":[[:space:]]*"([^"]+)".*/\1/p' |
      head -n 1
  )"
fi
[[ -n "$version" ]] || fail "could not determine the latest Topo release"

archive="topo-${platform}-${architecture}.zip"
url="https://github.com/$REPO/releases/download/$version/$archive"
download_dir="$(mktemp -d "${TMPDIR:-/tmp}/topo-install.XXXXXX")"
trap 'rm -rf "$download_dir"' EXIT

echo "Installing Topo $version for ${platform}-${architecture}..."
curl -fsSL --retry 5 --retry-all-errors "$url" -o "$download_dir/$archive" || fail "failed to download $url"
unzip -q "$download_dir/$archive" -d "$download_dir/extracted"
[[ -f "$download_dir/extracted/topo" ]] || fail "release archive has no topo binary"

mkdir -p "$INSTALL_DIR"
install -m 0755 "$download_dir/extracted/topo" "$INSTALL_DIR/.topo.new"
mv -f "$INSTALL_DIR/.topo.new" "$INSTALL_DIR/topo"
"$INSTALL_DIR/topo" --version

add_to_path() {
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "$INSTALL_DIR" >> "$GITHUB_PATH"
    return
  fi

  shell_name="$(basename "${SHELL:-/bin/sh}")"
  case "$shell_name" in
    zsh)
      config_file="${ZDOTDIR:-$HOME}/.zshrc"
      path_line='export PATH="$HOME/.topo/bin:$PATH"'
      ;;
    fish)
      config_file="${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish"
      path_line='fish_add_path $HOME/.topo/bin'
      ;;
    bash)
      config_file="$HOME/.bashrc"
      path_line='export PATH="$HOME/.topo/bin:$PATH"'
      ;;
    *)
      config_file="$HOME/.profile"
      path_line='export PATH="$HOME/.topo/bin:$PATH"'
      ;;
  esac

  mkdir -p "$(dirname "$config_file")"
  if [[ ! -f "$config_file" ]] || ! grep -Fq '.topo/bin' "$config_file"; then
    printf '\n# Added by the Topo installer\n%s\n' "$path_line" >> "$config_file"
    echo "Added Topo to PATH in $config_file; restart your terminal."
  fi
}

if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
  add_to_path
fi

echo "Topo is installed at $INSTALL_DIR/topo"
