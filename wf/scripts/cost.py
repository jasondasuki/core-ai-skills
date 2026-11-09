#!/usr/bin/env python3
"""Token cost of recent dynamic-workflow runs, per phase and model.
Usage: cost.py N PROJECTS_DIR [PROJECTS_DIR ...] [--scan MODEL] [--verify MODEL] [--max AGENTS]
  N: most recent runs to show. PROJECTS_DIR: a Claude Code projects folder.
  --scan/--verify/--max: flag phases off their stage model and runs over the agent cap."""
import argparse, glob, json, os
from collections import defaultdict
from datetime import datetime

ap = argparse.ArgumentParser(usage=__doc__)
ap.add_argument("n", type=int)
ap.add_argument("dirs", nargs="+")
ap.add_argument("--scan")
ap.add_argument("--verify")
ap.add_argument("--max", type=int)
a = ap.parse_args()

runs = {os.path.realpath(d) for p in a.dirs
        for d in glob.glob(f"{os.path.expanduser(p)}/*/*/subagents/workflows/wf_*")}
runs = sorted(runs, key=os.path.getmtime, reverse=True)[:a.n]
if not runs:
    raise SystemExit(f"No workflow runs found under: {' '.join(a.dirs)}")

K = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
STAGES = ((a.scan, ("scan", "search", "list", "fetch")), (a.verify, ("verify", "validate", "judge")))

def fmt(x): return f"{x/1e6:.2f}M" if x >= 1e6 else f"{x/1e3:.0f}k" if x >= 1e3 else str(x)
def ts(s): return datetime.fromisoformat(s.replace("Z", "+00:00"))

def flag(ph, model):
    for want, words in STAGES:
        if want and any(w in ph.lower() for w in words) and want not in model:
            return f"! want {want}"
    return ""

def active_minutes(spans):
    # union of per-agent [first, last] spans, so idle gaps before a resume don't count
    total, end = 0, None
    for s, e in sorted(spans):
        if end is None or s > end:
            total, end = total + (e - s).total_seconds(), e
        elif e > end:
            total, end = total + (e - end).total_seconds(), e
    return int(total // 60)

for run in runs:
    phase = {}
    if not os.path.exists(f"{run}/journal.jsonl"):
        print(f"\n{os.path.basename(run)}: no journal.jsonl, skipped")
        continue
    with open(f"{run}/journal.jsonl") as f:
        for line in f:
            e = json.loads(line)
            if e.get("type") == "started":
                phase[e["agentId"]] = e.get("phase") or "-"
    rows = defaultdict(lambda: {"agents": set(), **{k: 0 for k in K}})
    spans = []
    for path in glob.glob(f"{run}/agent-*.jsonl"):
        aid = os.path.basename(path)[6:-6]
        msgs, times = {}, []  # one usage per message id; streamed blocks repeat it
        with open(path) as f:
            for line in f:
                e = json.loads(line)
                if t := e.get("timestamp"):
                    times.append(ts(t))
                m = e.get("message") or {}
                if m.get("usage") and m.get("id"):
                    msgs[m["id"]] = (m.get("model", "?"), m["usage"])
        if times:
            spans.append((min(times), max(times)))
        for model, u in msgs.values():
            r = rows[(phase.get(aid, "-"), model.replace("claude-", ""))]
            r["agents"].add(aid)
            for k in K:
                r[k] += u.get(k) or 0
    dur = f", {active_minutes(spans)} min active" if spans else ""
    total = {k: sum(r[k] for r in rows.values()) for k in K}
    agents = len(set().union(*(r["agents"] for r in rows.values()))) if rows else 0
    over = f"  ! over cap of {a.max}" if a.max and agents > a.max else ""
    # headline = what drives the bill; cache reads cost ~0.1x input, so they only go in brackets
    print(f"\n{os.path.basename(run)}: {agents} agents{dur}, "
          f"{fmt(total['cache_creation_input_tokens'])} cache wr + {fmt(total['output_tokens'])} output "
          f"({fmt(sum(total.values()))} total incl. cache reads){over}")
    print(f"{'phase':<14}{'model':<14}{'agents':>7}{'input':>9}{'cache wr':>10}{'cache rd':>10}{'output':>9}  flag")
    for (ph, model), r in sorted(rows.items(), key=lambda kv: -sum(kv[1][k] for k in K)):
        print(f"{ph[:13]:<14}{model[:13]:<14}{len(r['agents']):>7}{fmt(r['input_tokens']):>9}"
              f"{fmt(r['cache_creation_input_tokens']):>10}{fmt(r['cache_read_input_tokens']):>10}"
              f"{fmt(r['output_tokens']):>9}  {flag(ph, model)}")
