#!/usr/bin/env python3
"""Token cost of recent dynamic-workflow runs, per phase and model.
Usage: cost.py N PROJECTS_DIR [PROJECTS_DIR ...]
  N: most recent runs to show. PROJECTS_DIR: a Claude Code projects folder."""
import glob, json, os, sys
from collections import defaultdict
from datetime import datetime

if len(sys.argv) < 3:
    sys.exit(__doc__)
n = int(sys.argv[1])
runs = {os.path.realpath(d) for p in sys.argv[2:]
        for d in glob.glob(f"{os.path.expanduser(p)}/*/*/subagents/workflows/wf_*")}
runs = sorted(runs, key=os.path.getmtime, reverse=True)[:n]
if not runs:
    sys.exit(f"No workflow runs found under: {' '.join(sys.argv[2:])}")

K = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")

def fmt(x): return f"{x/1e6:.2f}M" if x >= 1e6 else f"{x/1e3:.0f}k" if x >= 1e3 else str(x)

for run in runs:
    phase = {}
    with open(f"{run}/journal.jsonl") as f:
        for line in f:
            e = json.loads(line)
            if e.get("type") == "started":
                phase[e["agentId"]] = e.get("phase") or "-"
    rows = defaultdict(lambda: {"agents": set(), **{k: 0 for k in K}})
    times = []
    for path in glob.glob(f"{run}/agent-*.jsonl"):
        aid = os.path.basename(path)[6:-6]
        msgs = {}  # one usage per message id; streamed blocks repeat it
        with open(path) as f:
            for line in f:
                e = json.loads(line)
                if ts := e.get("timestamp"):
                    times.append(ts)
                m = e.get("message") or {}
                if m.get("usage") and m.get("id"):
                    msgs[m["id"]] = (m.get("model", "?"), m["usage"])
        for model, u in msgs.values():
            r = rows[(phase.get(aid, "-"), model.replace("claude-", ""))]
            r["agents"].add(aid)
            for k in K:
                r[k] += u.get(k) or 0
    dur = ""
    if times:
        t = sorted(times)
        p = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
        dur = f", {int((p(t[-1]) - p(t[0])).total_seconds() // 60)} min"
    total = {k: sum(r[k] for r in rows.values()) for k in K}
    agents = len(set().union(*(r["agents"] for r in rows.values()))) if rows else 0
    print(f"\n{os.path.basename(run)}: {agents} agents{dur}, "
          f"{fmt(sum(total.values()))} tokens ({fmt(total['output_tokens'])} output)")
    print(f"{'phase':<14}{'model':<14}{'agents':>7}{'input':>9}{'cache wr':>10}{'cache rd':>10}{'output':>9}")
    for (ph, model), r in sorted(rows.items(), key=lambda kv: -sum(kv[1][k] for k in K)):
        print(f"{ph[:13]:<14}{model[:13]:<14}{len(r['agents']):>7}{fmt(r['input_tokens']):>9}"
              f"{fmt(r['cache_creation_input_tokens']):>10}{fmt(r['cache_read_input_tokens']):>10}"
              f"{fmt(r['output_tokens']):>9}")
