---
name: paid-listing
description: "Handles a directory that charges a fee. The hirer approves the price and presses pay."
---

# Paid listing

Only in a chat with the hirer.

1. Run `.skills/paid-listing/scripts/run.py quote-listing --mcp <id> --directory <key>`.
2. Tell the hirer the directory, the exact price and what it buys. Wait for a clear yes.
3. If they have no card saved, run `card-link --mcp <id> --directory <key>` and send the link. The card stays in Seren Passwords. Never ask for a card number in chat.
4. After the yes, say: "I'm opening the checkout. Enter your saved card from Seren Passwords, check the amount and press pay."
5. Run `checkout --mcp <id> --directory <key> --hirer-said-yes`.
6. Confirm what was paid. If it returns `checkout_not_captured`, tell the hirer this directory's checkout isn't ready yet and that you've skipped it.
