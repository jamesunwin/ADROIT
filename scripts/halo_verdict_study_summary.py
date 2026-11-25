"""Summarise the physics-extensions verdict study (verdict_study.json): per portal and overall, the recorded status
(R3, before the relic and halo changes), the status now with each experiment's published halo (the relic change and
the audit repairs alone), and over the preset region (the halo label); the crossings' Ωh² under the new relic table
(each was on the old 0.12 contour)."""
import collections
import json
import sys

rows = json.load(open(sys.argv[1]))
total = len(rows)
published = collections.Counter((r["recorded"], r["published"].get("status", "error")) for r in rows.values())
region = collections.Counter((r["published"].get("status", "error"), r["region"].get("halo") or r["region"].get("status", "error"))
                             for r in rows.values())
errors = [(k, r[m]["error"]) for k, r in rows.items() for m in ("published", "region") if "error" in r[m]]
print(f"{total} crossings")
print("recorded -> published halo:")
for (a, b), n in sorted(published.items(), key=lambda kv: -kv[1]):
    print(f"  {a:9s} -> {b:9s} {n}")
print("published -> over the region:")
for (a, b), n in sorted(region.items(), key=lambda kv: -kv[1]):
    print(f"  {a:9s} -> {b:45s} {n}")
shifts = sorted(r["published"].get("omega_h2") / 0.12 - 1 for r in rows.values()
                if isinstance(r["published"].get("omega_h2"), (int, float)))
if shifts:
    print(f"Ωh²/0.12 − 1 at the old crossings: median {100 * shifts[len(shifts) // 2]:+.2f}%, range "
          f"{100 * shifts[0]:+.2f}% to {100 * shifts[-1]:+.2f}% ({len(shifts)} computed)")
by_entry = collections.defaultdict(collections.Counter)
for r in rows.values():
    by_entry[r["entry"]][r["region"].get("halo") or r["region"].get("status", "error")] += 1
print("per portal, over the region:")
for entry, counts in sorted(by_entry.items()):
    print(f"  {entry:32s} " + ", ".join(f"{k}: {v}" for k, v in counts.most_common()))
changed = [k for k, r in rows.items() if r["recorded"] != r["published"].get("status")]
print(f"status changed with the published halos: {len(changed)}: {changed[:12]}")
seconds = [r[m].get("seconds", 0) for r in rows.values() for m in ("published", "region")]
print(f"errors: {len(errors)} {errors[:3]}; mean seconds per crossing {sum(seconds) / max(total, 1):.0f}")
