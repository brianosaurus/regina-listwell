---
name: daily-report
description: "Builds, sends and records the one report Regina emails the hirer each day."
---

# Daily report

1. Run `.skills/daily-report/scripts/run.py build-report --timezone <tz>`. If it returns `already_sent`, stop.
2. Send the returned `subject` and `report` exactly as built with `seren_notify_owner`, kind `report`. Never shorten or reword them.
3. Only after Core confirms delivery, run `record-report --timezone <tz> --stdin-text`, passing the exact text you sent on standard input.
4. If Core refuses the report, show it in chat and use `seren_report_issue`. Never record a report that wasn't delivered.
