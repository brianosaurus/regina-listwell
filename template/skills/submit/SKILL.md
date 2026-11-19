---
name: submit
description: "Sends each approved MCP to each directory, and runs the official registry sign-in."
---

# Submit

1. Run `.skills/submit/scripts/run.py submit-work`. In a chat, add `--chat` so a human check can open the live window.
2. Read each result:
   - `submitted`: say which directory and link.
   - `needs_owner`: the question is saved. Ask it in a chat, or leave it for the daily report.
   - `draft_update_email`: write the update email and follow the `answers` skill to send it.
   - `blocked`: read `message`. Fix what you can and report the rest.
   - `failed` with `publisher_access_required`: request access to that publisher.
3. Before a list needs a `section`, run `list-sections --owner <owner> --repo <repo>`, pick the best anchor and save it with `save-answers`.
4. For a web form, read `page_text`. If it doesn't confirm the submission, tell the hirer exactly what the page said.

## Official registry, only in a chat

1. Run `registry-start --mcp <id>`.
2. Tell the hirer: "Go to `go_to` and enter `code`, then tell me when it's done."
3. After they confirm, run `registry-finish --mcp <id>`. If it returns `registry_waiting`, ask them to finish the approval.
