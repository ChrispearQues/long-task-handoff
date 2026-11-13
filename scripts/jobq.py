#!/usr/bin/env python3
"""任务队列：把长任务交给 worker agent，主会话不被占住。

  jobq.py submit --title "标题" --task "给 worker 的完整指令" [--out DIR] [--kind agent]
  jobq.py next --worker W1        # worker 领取一个（原子，防止重复领）
  jobq.py complete <id> --result "一行结论" [--file PATH]
  jobq.py fail <id> --error "原因"
  jobq.py list [--all]
  jobq.py show <id>
  jobq.py reap                    # 把超时未完成的标为 stale

状态: ~/.openclaw/state/jobq.json ；每个任务目录: ~/.openclaw/jobs/<id>/
"""
import argparse, json, os, secrets, sys, time
from datetime import datetime, timedelta

STATE = os.path.expanduser(os.environ.get('JOBQ_STATE', '~/.openclaw/state/jobq.json'))
ROOT = os.path.expanduser(os.environ.get('JOBQ_ROOT', '~/.openclaw/jobs'))
STALE_MIN = int(os.environ.get('JOBQ_STALE_MIN', '45'))


def load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def save(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(d, open(STATE, 'w'), ensure_ascii=False, indent=1)


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def submit(title, task, out, kind, max_min):
    d = load()
    jid = time.strftime('%m%d%H%M') + '-' + secrets.token_hex(2)
    jdir = os.path.join(ROOT, jid)
    os.makedirs(jdir, exist_ok=True)
    open(os.path.join(jdir, 'TASK.md'), 'w').write(f'# {title}\n\n{task}\n')
    d[jid] = {'id': jid, 'title': title, 'task': task, 'kind': kind, 'dir': jdir,
              'out': os.path.abspath(out) if out else jdir,
              'status': 'pending', 'created': now(), 'max_min': max_min,
              'started': None, 'finished': None, 'result': None, 'file': None,
              'error': None, 'worker': None}
    save(d)
    print(f'已提交 {jid}  {title}')
    print(f'  任务文件: {jdir}/TASK.md')
    print(f'  输出目录: {d[jid]["out"]}')
    return 0


def next_job(worker):
    d = load()
    for jid, j in sorted(d.items()):
        if j['status'] == 'pending':
            j.update({'status': 'running', 'started': now(), 'worker': worker or 'w1'})
            save(d)
            print(f'JOB {jid}')
            print(f'TITLE {j["title"]}')
            print(f'DIR {j["dir"]}')
            print(f'OUT {j["out"]}')
            print(f'MAXMIN {j["max_min"]}')
            print('---TASK---')
            print(j['task'])
            print('---END---')
            return 0
    print('NO_JOB')
    return 0


def complete(jid, result, file):
    d = load(); j = d.get(jid)
    if not j:
        print('没有这个任务'); return 2
    j.update({'status': 'done', 'finished': now(), 'result': result,
              'file': os.path.abspath(file) if file else None})
    save(d)
    print(f'完成 {jid}: {result}')
    return 0


def fail(jid, error):
    d = load(); j = d.get(jid)
    if not j:
        print('没有这个任务'); return 2
    j.update({'status': 'failed', 'finished': now(), 'error': error})
    save(d)
    print(f'失败 {jid}: {error}')
    return 0


def show(jid):
    d = load(); j = d.get(jid)
    if not j:
        print('没有这个任务'); return 2
    for k in ('id', 'title', 'status', 'created', 'started', 'finished', 'result', 'file', 'error', 'worker', 'out'):
        if j.get(k) is not None:
            print(f'{k}: {j[k]}')
    print('---TASK---'); print(j['task'])
    return 0


def list_jobs(all_=False):
    d = load()
    if not d:
        print('队列空'); return 0
    rows = sorted(d.values(), key=lambda x: x['created'], reverse=True)
    if not all_:
        rows = [r for r in rows if r['status'] in ('pending', 'running')] or rows[:5]
    for r in rows:
        print(f"{r['id']}  {r['status']:<8} {r['created']}  {r['title']}"
              + (f"  → {r['result']}" if r.get('result') else '')
              + (f"  ✗ {r['error']}" if r.get('error') else ''))
    return 0


def reap():
    d = load(); n = 0
    for j in d.values():
        if j['status'] == 'running' and j.get('started'):
            try:
                st = datetime.strptime(j['started'], '%Y-%m-%d %H:%M')
            except Exception:
                continue
            if datetime.now() - st > timedelta(minutes=STALE_MIN):
                j.update({'status': 'stale', 'error': f'超过 {STALE_MIN} 分钟未完成'}); n += 1
    save(d)
    print(f'标记 {n} 个超时任务为 stale')
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    s = sub.add_parser('submit')
    s.add_argument('--title', required=True); s.add_argument('--task', required=True)
    s.add_argument('--out'); s.add_argument('--kind', default='agent'); s.add_argument('--max-min', type=int, default=8)
    s = sub.add_parser('next'); s.add_argument('--worker', default='w1')
    s = sub.add_parser('complete'); s.add_argument('id'); s.add_argument('--result', required=True); s.add_argument('--file')
    s = sub.add_parser('fail'); s.add_argument('id'); s.add_argument('--error', required=True)
    s = sub.add_parser('show'); s.add_argument('id')
    s = sub.add_parser('list'); s.add_argument('--all', action='store_true')
    sub.add_parser('reap')
    a = ap.parse_args()
    if a.cmd == 'submit': return submit(a.title, a.task, a.out, a.kind, a.max_min)
    if a.cmd == 'next': return next_job(a.worker)
    if a.cmd == 'complete': return complete(a.id, a.result, a.file)
    if a.cmd == 'fail': return fail(a.id, a.error)
    if a.cmd == 'show': return show(a.id)
    if a.cmd == 'list': return list_jobs(a.all)
    if a.cmd == 'reap': return reap()
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main())
