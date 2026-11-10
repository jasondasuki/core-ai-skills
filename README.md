# core-ai-skills

Portable cores for personal agent skills. Each directory here is the
general function of one skill. The machine-specific half (a thin handler holding
the working directory, model, effort, MCP server names, and references to
secrets) lives next to the agent runtime's skills directory on each computer, never
here.

```
<skill-name>/SKILL.md      core: what the skill does, with {{VARIABLE}} placeholders
<skill-name>/references/   longer docs the core loads on demand
<skill-name>/scripts/      deterministic helpers
```

## Install

Needs `git`, `bash`, and an agent runtime that loads skills from a folder (for
Claude Code that is `.claude/skills` in your home folder).

```bash
git clone https://github.com/jasondasuki/core-ai-skills.git
bash core-ai-skills/install.sh <skills-dir>
```

The installer asks for a model, an effort and a subagent model, then writes the
first two handlers (`personal-skill-generator` and `onboard-skills`). Start a new
agent session and say **onboard skills**: it creates a handler for every other
skill and asks one batch of questions. Re-running the installer is safe; it never
overwrites a handler.

Prefer to let an agent do all of it, or want to know what each step does? Point
the agent at [ONBOARDING.md](ONBOARDING.md).

## Update

Nothing to run for existing skills: every skill fast-forwards this repo to the
latest `main` before it runs (set `PREFLIGHT_FF=0` to turn that off). Say
**onboard skills** to pick up skills added since you installed. Your handlers hold
your own values and are never changed by an update.

## Maintain

Create and maintain skills with `personal-skill-generator`. Check one pair with:

```bash
bash personal-skill-generator/scripts/check-skill.sh <core-dir> <handler-dir>
```

The cores must stay free of absolute paths, model IDs, MCP server names, and
credentials; the checker enforces that. `.workspaces/` holds test runs and is
git-ignored.
