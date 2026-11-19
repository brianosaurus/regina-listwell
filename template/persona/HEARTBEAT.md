# Daily work

Replace `<tz>` with the IANA time zone your schedule runs in. If a step fails, note it and go on to the next one.

1. `.skills/scout/scripts/run.py discover`, then follow the `scout` skill for each new site.
2. `.skills/freshen/scripts/run.py check`, then follow the `freshen` skill for each change.
3. `.skills/submit/scripts/run.py submit-work`, then follow the `submit` skill for each result.
4. `.skills/answers/scripts/run.py collect`, then follow the `answers` skill for each item.
5. `.skills/freshen/scripts/run.py confirm-listings`.
6. Follow the `daily-report` skill with `--timezone <tz>`.

Never open a live window on a scheduled run. Save what needs the hirer for the report.
