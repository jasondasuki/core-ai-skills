# Contributing

Fork the repository and open a pull request against `main`. Only the maintainer
can push to `main`.

- A skill is a folder with a `SKILL.md` core. Keep cores portable: no absolute
  paths, model IDs, MCP tool names, or credentials. Machine values are
  double-brace placeholders listed in the core's "Variables this skill expects"
  table.
- Before opening the pull request, run `.github/scripts/scan-repo.sh` and, for a
  core you changed, `bash personal-skill-generator/scripts/check-skill.sh <core-dir> <handler-dir>`.
  CI runs the scan, the unit tests and a test install.
- Commit with your GitHub noreply address; the author email becomes public.
- Security issues go through [SECURITY.md](SECURITY.md), not a public issue.
