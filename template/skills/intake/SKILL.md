---
name: intake
description: "Takes a hirer's MCP links, builds each listing pack and gets it approved."
---

# Intake

Ask only for what you can't find yourself: the MCP links, and the GitHub repository if there is one.

1. Run `.skills/intake/scripts/run.py add-mcp --url <link>`, adding `--repository <url>` when there is one.
2. Read the result's `probe`, plus the MCP's website and repository with `read-page`.
3. Write the listing pack and save it with `save-pack --stdin`, passing `{"mcp_id": <id>, "pack": {...}}`:
   - `name`, `short_description` (100 characters at most), `description`, `homepage_url`, `mcp_url`;
   - `transport`: `streamable-http` or `sse`;
   - `auth`: `none`, `api_key` or `oauth`;
   - `contact_email`: ask the hirer which address directories should use;
   - `repository_url`, `license`, `logo_url`, `pricing`, `privacy_url`, `support_url` and `tools` when known.
4. Show the hirer the pack and ask for one yes.
5. After the yes, run `approve-pack --mcp <id>`.
6. When the hirer answers a directory's question, run `save-answers --stdin` with `{"mcp_id": <id>, "directory_key": "<key>", "answers": {"<ask key>": "<answer>"}}`. Answer an ask yourself when the pack already tells you, such as choosing a category.
