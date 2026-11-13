#!/usr/bin/env python3
"""检查后台渲染任务有没有新完成的；只报一次。

用法: video_job_watch.py [--json]
退出码: 0 = 无新完成, 1 = 有新完成（stdout 为可播报文本）
"""
import json, os, sys
from datetime import datetime

STATE = os.path.expanduser(os.environ.get('VIDEO_JOB_STATE', '~/.openclaw/state/video_jobs.json'))
SEEN = os.path.expanduser(os.environ.get('VIDEO_JOB_SEEN', '~/.openclaw/state/video_jobs_reported.json'))


def alive(pid):
    try:
        os.kill(pid, 0); return True
    except Exception:
        return False


def main():
    try:
        jobs = json.load(open(STATE))
    except Exception:
        return 0
    try:
        seen = json.load(open(SEEN))
    except Exception:
        seen = {}
    new = []
    for jid, j in jobs.items():
        if j.get('status') == 'running' and not alive(j.get('pid', 0)):
            j['status'] = 'finished'
        if j.get('status') in ('finished', 'killed') and jid not in seen:
            seen[jid] = j.get('status')
            new.append(j)
    if new:
        os.makedirs(os.path.dirname(SEEN), exist_ok=True)
        json.dump(seen, open(SEEN, 'w'))
        json.dump(jobs, open(STATE, 'w'), ensure_ascii=False, indent=1)
        print(f'🎬 {len(new)} 个渲染任务结束：')
        for j in new:
            tail = ''
            try:
                tail = open(j['log'], errors='ignore').read().strip().splitlines()[-1][:120]
            except Exception:
                pass
            print(f"- {j['name']}（{j['id']}，{j['status']}）{('· ' + tail) if tail else ''}")
        print('回我一句我就把成片发过来（附件不在自动播报里发）。')
        return 1
    if any(j.get('status') == 'running' for j in jobs.values()):
        json.dump(jobs, open(STATE, 'w'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
