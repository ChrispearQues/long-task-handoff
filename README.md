# long-task-handoff

> **English** | [中文](README.zh-CN.md)

A skill for [OpenClaw](https://openclaw.ai) that stops long work from blocking the conversation.

Chat platforms tie *reply permission* to *the user's message*. On QQ, one inbound message grants five replies within five minutes. An agent turn that runs ten minutes cannot deliver its answer, and the API still returns `200 OK`. The work finishes, the user hears nothing, and both sides conclude the bot is stuck.

This skill removes that coupling. Long work moves out of the turn into one of three lanes, the agent keeps answering immediately, and completion is reported proactively.

```
user ──> chat-facing agent  ── short work (under ~2 min): answer in the turn
              │
              └─ long work ──> job card on disk (~/.openclaw/jobs)
                                    │
                          worker (isolated session, polled by cron)
                                    │  executes, writes artifacts
                                    └─ announces: "job done: <title> - <one line>"
                                                    │
                                        user says one word ──> agent sends details
```

## Three lanes

| Lane | Use for | Tool | Token cost |
|---|---|---|---|
| Process | render, transcode, batch OCR | `scripts/video_job.py` | none |
| Agent | work needing model reasoning | `scripts/jobq.py` + worker cron | model tokens |
| Staged | tasks that must span turns | `scripts/task_stage.py` | model tokens |

## Contents

| File | Purpose |
|---|---|
| `SKILL.md` | Operating instructions: lanes, hard rules, pitfalls, non-goals |
| `scripts/jobq.py` | Durable job queue: submit, atomic claim, complete, fail, reap |
| `scripts/video_job.py` | Detached process runner (`setsid`): start, list, status, log, stop |
| `scripts/video_job_watch.py` | One-shot "what finished" reporter for cron |
| `scripts/task_stage.py` | Staged protocol with resumable state |
| `examples/cron-worker.md` | Copy-paste cron definition for the worker |

## Quick start

```bash
# 1) submit work instead of doing it in the turn
python3 scripts/jobq.py submit --title "Weekly report" \
  --task "Read notes/*.md, produce a 1-page summary at OUT/summary.md" \
  --out /tmp/report

# 2) register the worker cron (see examples/cron-worker.md) - it polls every 5 minutes

# 3) later, read the result
python3 scripts/jobq.py show <id>
```

For CPU-only work, skip the queue entirely:

```bash
python3 scripts/video_job.py start --name ep12 -- ffmpeg -y -i in.mp4 -c:v libx264 out.mp4
python3 scripts/video_job.py list
```

## Four facts this skill is built on

Each one came from a production failure, not from documentation:

1. **The passive window is anchored to the user's message.** The bot's own messages do not extend it. Sending "still working" at minute four spends one of five replies and still expires at minute five.
2. **Isolated sessions deliver proactively** and are not bound by that window. This is why the worker can run for fifteen minutes and still report back.
3. **One failing tool call suppresses the whole reply.** A bare `mkdir` on an existing directory marked a completed job as failed, and the completion message was dropped. Every command in a worker must be failure-tolerant.
4. **Proactive delivery cannot attach files.** Announcements carry text only. Attachments must be sent by the channel-facing session in a normal reply.

## Design notes

- **Atomic claim.** Status flips to `running` before the task body is printed, so two workers never take the same job.
- **Durable by default.** Queue state and task bodies live on disk. A gateway restart loses nothing.
- **Process isolation.** `video_job.py` starts with `setsid`, so renders survive session teardown, restarts, and disconnects.
- **Cheap polling.** The worker runs with a small context most of the time, because the common tick returns `NO_JOB`.
- **Failure is visible.** `failureAlert` plus `reap` mean a broken worker does not look identical to an idle one.

## Non-goals

- **Not a guarantee of delivery.** Platform-side delivery is best effort. Only an acknowledgement from the user proves receipt.
- **Not a speedup.** The goal is non-blocking, not faster encoding.
- **Not a scheduler replacement.** Use cron for periodic work.

## Requirements

- Python 3.9+ (standard library only)
- `ffmpeg` on PATH if the commands you submit need it
- OpenClaw with cron and isolated sessions available

## Licence

MIT
