---
name: wf
description: Run a task as a Claude Code dynamic workflow with cost-aware defaults (/wf <task>), or show the token cost of recent workflow runs per phase and model (/wf cost [N]). Invoked only by typing /wf (model invocation is off).
---

# wf

Runs a task as a dynamic workflow with fixed cost defaults (agent cap, a cheap model for scan
stages, a mid model for verify stages), or reports what recent workflow runs cost per phase and
model so the defaults can be tuned. Claude Code only: it needs the Workflow tool.

## Variables this skill expects

| Variable | Meaning |
|---|---|
| `{{WORKDIR}}` | Working directory for all commands |
| `{{OUTPUT_DIR}}` | Unused; the answer is the reply in chat |
| `{{CORE_DIR}}` | This core's directory, for the cost script |
| `{{PROJECTS_DIRS}}` | Space-separated Claude Code projects folders that hold workflow run journals |
| `{{MAX_AGENTS}}` | Agent count to stay under per workflow |
| `{{SCAN_MODEL}}` / `{{SCAN_EFFORT}}` | Model and effort for scan, search, list and fetch stages |
| `{{VERIFY_MODEL}}` | Model for verify, judge, edit and write stages |
| `{{PROTECTED_SYSTEMS}}` | Systems no agent may change without the user's explicit approval for that exact change |

## Rules

- Invoking /wf is the user's explicit opt-in to a workflow; no other opt-in is needed.
- Anything the user names in the task (models, size, scope) overrides the defaults below.
- Read-only unless the task asks for changes. Nothing that changes `{{PROTECTED_SYSTEMS}}`.
  Why: workflow agents run unattended and cannot ask mid-run.
- Agents in one phase share model, effort, agentType and schema, so they share the prompt cache.

## Mode: cost

If the arguments start with `cost`, run:

```
python3 -I {{CORE_DIR}}/scripts/cost.py <N> {{PROJECTS_DIRS}} --scan {{SCAN_MODEL}} --verify {{VERIFY_MODEL}} --max {{MAX_AGENTS}}
```

N is the number after `cost` (default 1). Show the table as-is, then at most three lines: which
phase cost most, what the `!` flags say (a stage off its model, a run over the cap), and one
concrete change for next time. Cache reads
bill at about a tenth of fresh input, so judge cost by cache writes and output first.

## Mode: run (any other arguments)

The arguments are the task.

0. **Scout inline** (a few Glob/Grep/ls calls, no agents) to find the real work-list. If the task
   fits one session (roughly under 5 items or one file), say so and do it inline; no workflow,
   and skip step 1.
1. **Elaborate and confirm, inline** (no agent: the scout already holds the context). Rewrite
   the task as a precise prompt (goal, scope and where to look, what counts as done, output
   shape, constraints, anything ambiguous). Ask the user (AskUserQuestion if available): use it,
   edit it, or use the original. Put the full elaborated prompt in the `preview` of the "use it"
   option and the original task in the `preview` of "use the original". Why: while the question
   dialog is open the user sees only the dialog, not text written before it, so a prompt shown
   only in chat is invisible at the moment they choose. Without AskUserQuestion, print the
   prompt in a fenced block and end the turn with the question. Wait for the answer; the chosen text is the
   task from here on. Skip this step if the user says "no elaborate" in the arguments.
2. **Load** the `workflow-authoring` skill.
3. **Show the plan in 3-5 lines**: phases, agents per phase, model per phase, rough tokens (about
   40k setup per agent plus the work). Then launch; the Workflow permission prompt is the gate.
4. **Write the script** with these defaults:
   - At most `{{MAX_AGENTS}}` agents. For long lists, batch items per agent and `log()` anything
     dropped. Enforce it in code: route every call through this guard, never `agent()` directly:
     `let n = 0; const run = (p, o) => { if (++n > {{MAX_AGENTS}}) throw new Error('agent cap'); return agent(p, o) }`
   - Phase titles start with their stage word (`Scan`, `Search`, `List`, `Fetch`, `Verify`, `Edit`, `Write`,
     `Judge`, `Synthesize`), e.g. `Scan repos`. Why: Mode: cost checks each phase's model by
     that word and flags a phase called "Hunt" or "Recon" as `! no stage word`.
   - Verify and judge in batches of 5-10 items per agent, never one agent per item. Why: one
     verifier per finding is what blows past the cap.
   - Per `run()` call: scan, search, list, fetch → `model: '{{SCAN_MODEL}}', effort:
     '{{SCAN_EFFORT}}'`; verify, judge, edit and write → `model: '{{VERIFY_MODEL}}'`; final synthesis → omit
     `model` (session model).
   - `agentType: 'runner'` only for fixed mechanical checks, if that agent type exists.
   - Parallel file edits use `isolation: 'worktree'`.
   - **Check before launch:** reread the script and confirm every `run()` call has the model
     its stage needs (synthesis has none), that no bare `agent()` call remains, and that the
     worst-case agent count, including per-item fan-out, is at most `{{MAX_AGENTS}}`. Fix it before calling Workflow.
5. **When it completes**, give the result first, then one cost line from Mode: cost with N=1
   (agents, minutes, cache writes, output).
