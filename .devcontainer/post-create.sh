#!/usr/bin/env bash
# Runs once when the dev container is created: installs mise, the tools in mise.toml, the project
# dependencies and the Playwright browser. Start the app afterwards with `mise run dev`.
set -euo pipefail

# The dependency volumes are created as root; hand them to the container user.
sudo chown "$(id -u):$(id -g)" .venv apps/web/node_modules

curl -fsSL https://mise.run | sh
export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:$PATH"
for shell in bash zsh; do
  rc="$HOME/.${shell}rc"
  grep -q "mise activate" "$rc" 2>/dev/null || echo "eval \"\$(mise activate $shell)\"" >>"$rc"
done

mise install
# Node only as a runtime, as on laptops and CI runners: bunx and bun run hand tools with a node
# shebang (vite, playwright) to it. Under Bun alone the Playwright browser download fails TLS.
mise use --global node@lts
mise run setup
(cd apps/web && bunx playwright install --with-deps --only-shell chromium)
