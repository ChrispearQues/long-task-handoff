# Worker cron (isolated session)

Register one cron job that polls the queue. It must run in an isolated session, not the chat session, so it never blocks the conversation.

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
    "message": "You are a background job worker.\n\nRULE ZERO: end every exec command with `|| true` and create directories with `mkdir -p`. A non-zero exit marks the run as failed and suppresses your final message.\n\n1) jobq.py reap || true\n2) jobq.py next --worker cron || true\n3) If the output is only NO_JOB, reply exactly: NO_REPLY\n4) Otherwise read id/DIR/OUT/MAXMIN and the TASK body, do the work, write artifacts into OUT.\n5) jobq.py complete <id> --result \"<one line>\" || true   (or fail <id> --error \"...\")\n6) Reply with exactly one line: \"Job done: <title> - <conclusion>. Say go and I will send the details.\" Never emit MEDIA lines; proactive delivery cannot attach files."
  },
  "delivery": { "mode": "announce", "channel": "<channel>", "to": "<chat-target>" },
  "failureAlert": { "mode": "announce", "channel": "<channel>", "to": "<chat-target>", "after": 2, "cooldownMs": 1800000 }
}
```

Notes:

- `lightContext: true` keeps the per-tick cost low, since most ticks return `NO_JOB`.
- `timeoutSeconds` is the hard ceiling for one job. Keep it below whatever the scheduler tolerates, and keep `MAXMIN` in the task card lower still so the worker yields partial results instead of being killed.
- `failureAlert` matters: without it, a worker that fails every tick looks exactly like a worker with nothing to do.
