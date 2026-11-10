#!/usr/bin/env bash
# Bootstrap this repo on a computer: write the two handlers nothing else can
# generate (personal-skill-generator and onboard-skills) into the agent's skills
# directory, then check them. The "onboard skills" skill creates the rest.
# Usage: install.sh <skills-dir>
# Answers are prompted for, or taken from the environment (for scripts and CI):
#   MODEL EFFORT SUBAGENT_MODEL   required: written the way your agent runtime accepts them
#   DEFAULT_WORKDIR               default: the folder holding this repo
#   SUBAGENT_TYPE                 default: general-purpose
#   AGENT_SELECTION_FILE          default: UNSET (optional model tier policy file)
# Safe to re-run: an existing handler is never overwritten, only checked.
set -eu

skills_dir="${1:?usage: install.sh <skills-dir>   (the folder your agent reads personal skills from)}"
repo="$(cd "$(dirname "$0")" && pwd -P)"
gen="$repo/personal-skill-generator"
mkdir -p "$skills_dir"
skills_dir="$(cd "$skills_dir" && pwd -P)"

ask() { # ask <VAR> <question> [default]: keep the environment value, else prompt, else default
  local cur="${!1:-}"
  if [ -z "$cur" ] && [ -t 0 ]; then
    read -r -p "$2${3:+ [$3]}: " cur
  fi
  cur="${cur:-${3:-}}"
  [ -n "$cur" ] || { echo "install.sh: $1 is required (set it in the environment or run interactively)" >&2; exit 1; }
  # a "|" or a newline would break the handler's variable table
  case "$cur" in *"|"*|*$'\n'*) echo "install.sh: $1 must not contain '|' or a newline" >&2; exit 1 ;; esac
  printf -v "$1" '%s' "$cur"
}
ask MODEL "Model for skills"
ask EFFORT "Effort for skills"
ask SUBAGENT_MODEL "Model for subagents"
ask DEFAULT_WORKDIR "Default working directory for skills" "$(dirname "$repo")"
SUBAGENT_TYPE="${SUBAGENT_TYPE:-general-purpose}"
AGENT_SELECTION_FILE="${AGENT_SELECTION_FILE:-UNSET}"
[ -d "$DEFAULT_WORKDIR" ] || { echo "install.sh: DEFAULT_WORKDIR '$DEFAULT_WORKDIR' is not a directory" >&2; exit 1; }

row() { printf '| `%s` | `%s` | %s |\n' "$1" "$2" "$3"; }

write_handler() { # write_handler <name> <extra-rows>
  local name="$1" out="$skills_dir/$1/SKILL.md"
  if [ -e "$out" ]; then
    echo "exists, left unchanged: $out"
    return
  fi
  mkdir -p "$skills_dir/$name"
  NAME="$name" \
  DESCRIPTION="$(sed -n 's/^description:[[:space:]]*//p' "$repo/$name/SKILL.md" | head -n1)" \
  CORE_DIR="$repo/$name" CORE_BRANCH=main CORE_REMOTE=origin \
  PREFLIGHT_SCRIPT="$gen/scripts/preflight.sh" \
  MODEL="$MODEL" EFFORT="$EFFORT" SUBAGENT_MODEL="$SUBAGENT_MODEL" \
  AGENT_SELECTION_FILE="$AGENT_SELECTION_FILE" WORKDIR="$repo" OUTPUT_DIR="$repo" \
  EXTRA_ROWS="$2" SECRET_ROWS='| (none) | - | This skill needs no credentials |' \
  awk '
    # literal replacement: values come from ENVIRON so no character in them is special
    { while (match($0, /<<[A-Z_]+>>/)) {
        tok = substr($0, RSTART + 2, RLENGTH - 4)
        $0 = substr($0, 1, RSTART - 1) "\001" ENVIRON[tok] "\002" substr($0, RSTART + RLENGTH)
      }
      gsub(/[\001\002]/, ""); print }
  ' "$gen/templates/handler.SKILL.md" > "$out"
  echo "created: $out"
}

write_handler personal-skill-generator "$(
  row REPO_DIR "$repo" "Root of the default skills repo"
  row REPO_ROUTES UNSET "Routing from a skill's subject to another skill repo; none yet"
  row SKILLS_DIR "$skills_dir" "Where the agent runtime reads personal skills from"
  row DEFAULT_MODEL "$MODEL" "Model for a new skill when the user names none"
  row DEFAULT_EFFORT "$EFFORT" "Effort for a new skill when the user names none"
  row DEFAULT_SUBAGENT_MODEL "$SUBAGENT_MODEL" "Subagent model for a new skill when the user names none"
  row DEFAULT_WORKDIR "$DEFAULT_WORKDIR" "Working directory for a new skill when the user names none"
  row MODEL_ALIASES UNSET "Spoken model name to model ID"
  row WORKSPACES_DIR "$repo/.workspaces" "Test-run scratch area (git-ignored)"
  row SKILL_CREATOR UNSET "Skill to delegate testing to; set it to test and tune skills"
  row SKILL_CREATOR_DIR UNSET "Where that skill's scripts live"
)"

write_handler onboard-skills "$(
  row SKILL_REPO_DIRS "$repo" "The skill repos to sync and scan, comma-separated"
  row SKILLS_DIR "$skills_dir" "Where the agent runtime reads personal skills from"
  row GENERATOR_DIR "$gen" "The generator's core directory"
  row DEFAULT_MODEL "$MODEL" "Model written into new handlers"
  row DEFAULT_EFFORT "$EFFORT" "Effort written into new handlers"
  row DEFAULT_SUBAGENT_MODEL "$SUBAGENT_MODEL" "Subagent model written into new handlers"
  row DEFAULT_WORKDIR "$DEFAULT_WORKDIR" "Working and output directory written into new handlers"
  row SUBAGENT_EFFORT "$EFFORT" "Effort the drafting subagents work at"
  row SUBAGENT_TYPE "$SUBAGENT_TYPE" "Subagent type for the drafting subagents"
  row MAX_PARALLEL_SUBAGENTS 4 "Most drafting subagents to run at once"
)"

status=0
for name in personal-skill-generator onboard-skills; do
  bash "$gen/scripts/check-skill.sh" "$repo/$name" "$skills_dir/$name" | grep -E '^(ERROR|WARN|ok):|^        ' || true
  [ "${PIPESTATUS[0]}" -eq 0 ] || status=1
done
[ "$status" -eq 0 ] || { echo "install.sh: the checker found errors above"; exit 1; }

cat <<EOF

Installed. Next:
  1. Start a new agent session, so the two skills are listed.
  2. Say: onboard skills
     It creates a handler for every other skill in this repo and asks one batch of questions.
Rows marked UNSET in the handlers are optional; the agent can fill them later.
EOF
