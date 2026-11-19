---
name: freshen
description: "Notices changes to an MCP, its code or its website, and updates the listing pack."
---

# Freshen

1. Run `.skills/freshen/scripts/run.py check`. The first run records a starting point and reports no changes.
2. For each item in `changes`, compare `changed` with `pack`. Decide whether a listed fact changed: name, description, tools, address, sign-in method or price.
3. If a fact changed, write the corrected pack and run `save-pack --stdin --from-change`. That marks its live submissions for update, and `submit-work` sends them.
4. If no fact changed, do nothing. A new commit or a website edit alone doesn't justify an update.
5. Keep a one-line summary of each update for rejection replies and the daily report.
