# Worker cron (isolated session)

Register one cron job that polls the queue. It must run in an isolated session, not the chat session, so it never blocks the conversation.

Two rules decide whether this works in practice:

- **No narration.** Every sentence the worker emits can be delivered to the user's chat. It must stay silent unless it has a result.
- **Failure-tolerant commands.** A single non-zero exit marks the run as failed and suppresses the final message, so the work completes and nobody hears about it.

```json
{
  "name": "jobq-worker",
  "schedule": { "kind": "cron", "expr": "*/5 8-23 * * *", "tz": "Asia/Hong_Kong" },
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "model": "<cheap-fast-model>",
    "lightContext": true,
    "timeoutSeconds": 900,
    "message": "You are a background job worker in an isolated session.\n\nRULE ONE - no narration. Never print progress lines such as \"I'll start by checking the job queue\". Your output exists only as the final one-liner, or as the silent token.\nRULE TWO - every exec command ends with `|| true`, and directories are created with `mkdir -p`. A non-zero exit marks the run as failed and suppresses your final message.\n\n1) jobq.py reap || true\n2) jobq.py next --worker cron || true\n3) If the output is only NO_JOB, reply exactly: NO_REPLY\n4) Otherwise read id/DIR/OUT/MAXMIN and the TASK body, do the work, write artifacts into OUT.\n5) jobq.py complete <id> --result \"<one line>\" || true   (or fail <id> --error \"...\")\n6) Reply with exactly one line: \"Job done: <title> - <conclusion>. Say go and I will send the details.\" Never emit MEDIA lines; proactive delivery cannot attach files."
  },
  "delivery": { "mode": "announce", "channel": "<channel>", "to": "<chat-target>" },
  "failureAlert": { "mode": "announce", "channel": "<channel>", "to": "<chat-target>", "after": 2, "cooldownMs": 1800000 }
}
```

Notes:

- `lightContext: true` keeps the per-tick cost low, since most ticks return `NO_JOB`.
- `timeoutSeconds` is the hard ceiling for one job. Keep it below whatever the scheduler tolerates, and keep `MAXMIN` in the task card lower still so the worker yields partial results instead of being killed.
- `failureAlert` matters: without it, a worker that fails every tick looks exactly like a worker with nothing to do.
- After the first day, check `lastDelivered` on the job. A worker can run `ok` and still have its message dropped.
## The narration trap (cost a full rebuild to find)

In an isolated cron run, **every assistant message is delivered to the user**, not just the final one. A model that opens with "I'll check the job queue." sends that line to the user's phone as if it were the answer. Instruction wording matters:

- Weak: "do not narrate" - the model still narrates.
- Working: "Your session is isolated and **every sentence you emit is pushed to the user's phone**. You may not emit a single character before your first tool call."

Verify by reading the run transcript: the first assistant entry must be empty (tool call), and the last must be the one-liner or the silent token.
