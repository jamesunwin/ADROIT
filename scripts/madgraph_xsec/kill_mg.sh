#!/bin/bash
# Kill every MG5/MadEvent process working inside a given process-directory pattern (default: all of madgraph-xsec/work).
PAT=${1:-madgraph-xsec/work}
pkill -f "$PAT" 2>/dev/null
for pid in $(pgrep -f "madevent|check_sa|survey.sh|refine"); do
  if lsof -p $pid 2>/dev/null | grep cwd | grep -q "$PAT"; then kill $pid; fi
done
sleep 1
pgrep -fl "$PAT" || echo "nothing left for $PAT"
