---
inclusion: always
---

# Product: Carbon Copy

Carbon Copy brings back the old carbon-copy receipt book for the AI that handles a small business's money.

- **Who it is for:** a small business owner (our example is Maya, who runs a nine-person furniture workshop) whose AI agent pays supplier bills, sends refunds and answers disputes through PayPal.
- **The problem:** the AI can say it did a job it never did, or do something it never mentions, and today there is no record the owner can trust afterwards. A log the AI's own system writes can be edited by whoever controls that system.
- **What it does:** every money move the AI tries, every decision the checker makes, every tap the owner makes and the AI's end-of-day report each get a carbon copy at the moment they happen. Each copy carries the fingerprint of the copy before it and is signed. Anyone holding the copies and the public key can check them; one changed copy shows exactly where the book was altered.
- **What it is built on:** Receipts, our earlier open-source checker that sits between an AI agent and PayPal and checks PayPal's own records before money moves. The Receipts base is disclosed in the README and in the first commit.

Write every screen, message and error for the owner, not for a developer: plain words, no jargon on the first screen. Developer detail lives in a separate developer view and in the README's lower sections.
