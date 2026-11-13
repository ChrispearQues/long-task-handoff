---
name: "long-task-handoff"
description: "Keep chat agents responsive during long work: durable job queue, background process runner, staged protocol, announce-based completion."
---

# Long-Task Handoff

## When to use

Any task that will outlive a chat turn: video render, batch transcode, multi-document processing, long research, large refactors. Also use it whenever the reply must land on a channel that has a **passive-reply window** (QQ, and similar platforms).

## The problem

Chat platforms tie *reply permission* to *the user's message*. On QQ, an inbound message allows 5 replies within 5 minutes. A turn that runs 10 minutes cannot deliver its answer, and the API still returns `200 OK`, so the failure is silent. Meanwhile the agent is blocked, so the user sees nothing at all.

Three facts, each verified by experiment:

1. **The passive window is anchored to the user message.** The bot's own messages do not extend it. Sending "still working" at minute 4 spends one of the five replies and still dies at minute 5.
2. **Isolated sessions deliver proactively.** A cron / isolated-session run is not bound by that window, so long work can finish and still report back.
3. **One failing tool call suppresses the final message.** If any tool returns non-zero, the run is marked as an error and the assistant's reply is dropped. Every command in a background job must therefore be failure-tolerant (`|| true`, `mkdir -p`).

## Three lanes

| Lane | Use for | Tool | Cost |
|---|---|---|---|
| Process | render, transcode, batch OCR (pure CPU) | `video_job.py` | no tokens |
| Agent | work that needs model reasoning | `jobq.py` + worker cron | model tokens |
| Staged | tasks that must span several turns (needs user input between parts) | `task_stage.py` | model tokens |

Pick the cheapest lane that fits. Never run a long job inside the conversation turn itself.

## Lane 1: durable agent job queue

```bash
# submit (from the chat-facing session); the task text must be self-contained
jobq.py submit --title "Report on X" --task "Full instructions: goal, inputs, output paths, acceptance" --out /path/out

# worker side (cron, every N minutes, isolated session)
jobq.py reap                       # mark stale running jobs
jobq.py next --worker cron         # atomic claim, prints NO_JOB when empty
jobq.py complete <id> --result "one-line conclusion" --file /path/to/artifact
jobq.py fail <id> --error "reason"
jobq.py list --all
jobq.py show <id>
```

State lives in `~/.openclaw/state/jobq.json`, one directory per job under `~/.openclaw/jobs/<id>/` containing `TASK.md`. Claiming flips the status before returning, so two workers never grab the same job, and a gateway restart loses nothing.

The chat-facing agent should answer immediately with "submitted, I will report back", then stop.

## Lane 2: background process

```bash
video_job.py start --name "ep12" -- ffmpeg -y -i in.mp4 -c:v libx264 out.mp4
video_job.py list | status <id> | log <id> | stop <id> | prune
```

`start` uses `setsid` (`start_new_session=True`), so the process survives gateway restarts and session teardown. The call returns a job id in milliseconds, which is what keeps the turn short.

`video_job_watch.py` prints a one-shot report when jobs finish (dedup state in `~/.openclaw/state/video_jobs_reported.json`); exit code `1` means "something finished", `0` means "nothing new".

## Lane 3: staged protocol

For tasks that genuinely need the user between parts:

```bash
task_stage.py start "name" --stages "part one|part two|part three"
task_stage.py next        # advance and print the sentence to send
task_stage.py status      # resume after a lost reply
```

Keep each stage under 4 minutes, reply at the end of each stage, and ask the user for one short acknowledgement. That acknowledgement opens a fresh passive window. The state file means a dropped reply costs one `status` call rather than a restart.

## Install

1. Copy `scripts/*.py` into your workspace `scripts/` and `chmod +x`.
2. Add a cron worker: see `examples/cron-worker.md`. It runs in an isolated session, picks one job per tick, and announces completion.
3. Smoke test the queue without a model:

```bash
jobq.py submit --title t --task "write 42 into n.txt" --out /tmp/t1
jobq.py next --worker test      # should print the job
jobq.py next --worker test      # should print NO_JOB (atomic claim)
jobq.py complete <id> --result ok
jobq.py list --all
```

## Hard rules

1. **No long work inside the conversation turn.** Anything above roughly 2 minutes goes to a lane.
2. **Every shell command in a worker ends with `|| true`**, and directories are created with `mkdir -p`. A stray non-zero exit silently kills the announcement.
3. **The completion announcement carries text only.** Proactive delivery cannot attach files. Attachments must be sent by the channel-facing session in a normal reply.
4. **One attachment per message.** Multiple multi-megabyte files in one message get dropped silently.
5. **Do not start two renders of the same source.** Check `list` first; on small machines they starve each other.
6. **Report the job id and expected duration** the moment you submit, so the user knows the turn is not stuck.

## Pitfalls (all observed in production)

- **"Still working" does not extend the window.** Tempting, and wrong.
- **`mkdir` without `-p` killed an entire announcement.** The work completed, the file was written, and the user was still told nothing.
- **Restarting the render instead of checking status.** On an 8 GB machine two concurrent 1080p multiplane renders fought for CPU and were OOM-killed (`rc -9`) twice.
- **Assuming the announcement arrived because the tool returned success.** Verify with the channel's own delivery log where available.
- **Jobs left in `running` after a crash.** Run `reap` at the start of every worker tick.

## Non-goals

- This does not guarantee the user reads the result. Platform-side delivery is best effort; only an acknowledgement proves receipt.
- This does not make long work fast. It makes long work **non-blocking**.
- This does not replace a real scheduler for periodic tasks; cron already does that.

## Porting

The scripts are plain Python 3.9+ with no third-party dependency. `video_job.py` needs `ffmpeg` on PATH only if the commands you submit do. Override paths with `JOBQ_STATE`, `JOBQ_ROOT`, `VIDEO_JOB_STATE`, `TASK_STAGE_STATE`.

The lane concept is channel agnostic. The passive-window numbers quoted above are QQ specific; other platforms have different limits (or none), but the "do not block the turn" rule still pays off.
