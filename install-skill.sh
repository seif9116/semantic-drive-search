#!/usr/bin/env bash
# Semantic Drive Search — Claude Code skill installer
# Installs the /sds skill globally so it's available in all Claude Code sessions.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/seif9116/semantic-drive-search/master/install-skill.sh | bash
#   # or from a local clone:
#   ./install-skill.sh

set -euo pipefail

SKILL_NAME="sds"
SKILL_DIR="$HOME/.claude/skills/$SKILL_NAME"
REPO_URL="https://raw.githubusercontent.com/seif9116/semantic-drive-search/master"

# Colors (if terminal supports them)
if [ -t 1 ]; then
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  RED='\033[0;31m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  GREEN='' YELLOW='' RED='' BOLD='' RESET=''
fi

info()  { echo -e "${GREEN}[+]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $*"; }
error() { echo -e "${RED}[x]${RESET} $*"; }

echo ""
echo -e "${BOLD}Semantic Drive Search — Claude Code Skill Installer${RESET}"
echo "──────────────────────────────────────────────────────"
echo ""

# ── Step 1: Determine source (local clone vs remote) ─────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SOURCE=""

if [ -f "$SCRIPT_DIR/skills/sds/SKILL.md" ]; then
  SKILL_SOURCE="$SCRIPT_DIR/skills/sds/SKILL.md"
  info "Found skill file in local repo: $SKILL_SOURCE"
elif command -v curl &>/dev/null; then
  SKILL_SOURCE="remote"
  info "Will download skill from GitHub"
else
  error "No local skill file found and curl is not installed."
  exit 1
fi

# ── Step 2: Install the skill to ~/.claude/skills/sds/ ───────────────────────
info "Installing skill to $SKILL_DIR ..."
mkdir -p "$SKILL_DIR"

if [ "$SKILL_SOURCE" = "remote" ]; then
  curl -fsSL "$REPO_URL/skills/sds/SKILL.md" -o "$SKILL_DIR/SKILL.md"
else
  cp "$SKILL_SOURCE" "$SKILL_DIR/SKILL.md"
fi

info "Skill installed at $SKILL_DIR/SKILL.md"

# ── Step 3: Install the sds CLI ──────────────────────────────────────────────
if command -v sds &>/dev/null; then
  info "sds CLI already installed: $(command -v sds)"
else
  warn "sds CLI not found. Installing..."
  if command -v uv &>/dev/null; then
    uv pip install semantic-drive-search
  elif command -v pip &>/dev/null; then
    pip install semantic-drive-search
  elif command -v pip3 &>/dev/null; then
    pip3 install semantic-drive-search
  else
    error "No pip/uv found. Install manually: pip install semantic-drive-search"
  fi

  if command -v sds &>/dev/null; then
    info "sds CLI installed successfully"
  else
    warn "sds CLI installed but not on PATH. You may need to restart your shell."
  fi
fi

# ── Step 4: Register MCP server ──────────────────────────────────────────────
echo ""
info "Registering MCP server with Claude Code..."

if command -v claude &>/dev/null; then
  claude mcp add semantic-drive-search -- uv run sds-mcp 2>/dev/null && \
    info "MCP server registered (scope: user)" || \
    warn "MCP registration returned an error — it may already be configured"
else
  warn "claude CLI not found. Add the MCP server manually:"
  echo ""
  echo "  claude mcp add semantic-drive-search -- uv run sds-mcp"
  echo ""
fi

# ── Step 5: First-time setup hint ────────────────────────────────────────────
echo ""
echo "──────────────────────────────────────────────────────"
echo -e "${GREEN}${BOLD}Done!${RESET} The /sds skill is now available in Claude Code."
echo ""
echo "Next steps:"
echo "  1. Restart Claude Code (or start a new session)"
echo "  2. Run sds setup to configure your API keys and database"
echo "  3. Type /sds in Claude Code to use the skill"
echo ""
echo "Example usage in Claude Code:"
echo '  /sds find sunset photos'
echo '  /sds index https://drive.google.com/drive/folders/...'
echo '  /sds what folders are indexed?'
echo ""
