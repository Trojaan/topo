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

# Preserve the single-binary topo archive expected by existing topo upgrade.
[[ "$version" =~ ^v?([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || fail "invalid release version: $version"
commands=(topo)
if (( 10#${BASH_REMATCH[1]} > 0 || 10#${BASH_REMATCH[2]} >= 6 )); then
  commands+=(topo2)
fi
expected_version="${version#v}"
download_dir="$(mktemp -d "${TMPDIR:-/tmp}/topo-install.XXXXXX")"
trap 'rm -rf "$download_dir"' EXIT

echo "Installing Topo $version for ${platform}-${architecture}..."
# Validate every download before replacing any existing command.
for executable in "${commands[@]}"; do
  archive="${executable}-${platform}-${architecture}.zip"
  url="https://github.com/$REPO/releases/download/$version/$archive"
  curl -fsSL --retry 5 --retry-all-errors "$url" -o "$download_dir/$archive" || fail "failed to download $url"
  unzip -q "$download_dir/$archive" -d "$download_dir/$executable"
  downloaded="$download_dir/$executable/$executable"
  [[ -f "$downloaded" ]] || fail "release archive has no $executable binary"
  chmod +x "$downloaded"
  actual_version="$("$downloaded" --version)" || fail "$executable cannot run"
  [[ "$actual_version" = "$executable $expected_version" ]] || fail "$executable reports a different version"
done

mkdir -p "$INSTALL_DIR"
for executable in "${commands[@]}"; do
  install -m 0755 "$download_dir/$executable/$executable" "$INSTALL_DIR/.$executable.new"
  mv -f "$INSTALL_DIR/.$executable.new" "$INSTALL_DIR/$executable"
  "$INSTALL_DIR/$executable" --version
done

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

for executable in "${commands[@]}"; do
  echo "$executable is installed at $INSTALL_DIR/$executable"
done
