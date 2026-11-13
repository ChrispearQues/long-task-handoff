#!/usr/bin/env python3
"""把重的视频渲染丢到后台守护进程，agent 只拿 job id，不占对话回合。

用法:
  video_job.py start --name <名字> -- <命令...>      # 后台启动（setsid，脱离会话）
  video_job.py list                                  # 所有任务 + 状态/耗时
  video_job.py status <id>                           # 状态 + 末尾日志
  video_job.py log <id> [--lines 40]
  video_job.py stop <id>
  video_job.py prune                                 # 清理已结束的旧任务记录

为什么: 渲染动辄 5-20 分钟，会 (1) 撞 QQ 5 分钟被动回复窗口、
(2) 占满 8 核让主会话卡顿。后台进程与 agent 回合解耦，断线/重启都不影响渲染。
"""
import json, os, signal, subprocess, sys, time, uuid
from datetime import datetime

STATE = os.path.expanduser(os.environ.get('VIDEO_JOB_STATE', '~/.openclaw/state/video_jobs.json'))
JOBDIR = os.path.dirname(STATE) + '/video_jobs'


def load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def save(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(d, open(STATE, 'w'), ensure_ascii=False, indent=1)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def start(name, cmd):
    os.makedirs(JOBDIR, exist_ok=True)
    jid = time.strftime('%H%M%S') + '-' + uuid.uuid4().hex[:4]
    logp = os.path.join(JOBDIR, jid + '.log')
    with open(logp, 'w') as log:
        p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                             start_new_session=True, close_fds=True, cwd=os.getcwd())
    d = load()
    d[jid] = {'id': jid, 'name': name, 'cmd': cmd, 'pid': p.pid, 'log': logp,
              'started': datetime.now().isoformat(timespec='seconds'), 'status': 'running'}
    save(d)
    print(f'job {jid} started pid={p.pid}')
    print(f'   log: {logp}')
    print(f'   cmd: {" ".join(cmd[:6])}{" ..." if len(cmd) > 6 else ""}')
    return 0


def refresh(d):
    for j in d.values():
        if j['status'] == 'running' and not alive(j['pid']):
            j['status'] = 'finished'
            j['ended'] = datetime.now().isoformat(timespec='seconds')
    return d


def human(sec):
    return f'{int(sec//60)}m{int(sec%60):02d}s'


def cmd_list():
    d = refresh(load()); save(d)
    if not d:
        print('没有任务'); return 0
    for j in sorted(d.values(), key=lambda x: x['started'], reverse=True):
        el = ''
        try:
            t0 = datetime.fromisoformat(j['started']); t1 = datetime.now()
            el = human((t1 - t0).total_seconds())
        except Exception:
            pass
        print(f"{j['id']}  {j['status']:<9} {el:>7}  {j['name']}")
    return 0


def cmd_status(jid):
    d = refresh(load()); save(d)
    j = d.get(jid)
    if not j:
        print('没有这个 job'); return 2
    el = ''
    try:
        el = human((datetime.now() - datetime.fromisoformat(j['started'])).total_seconds())
    except Exception:
        pass
    print(f"{j['id']}  {j['name']}  status={j['status']}  elapsed={el}  pid={j['pid']}")
    if os.path.exists(j['log']):
        tail = open(j['log'], errors='ignore').read().splitlines()[-8:]
        print('--- log tail ---')
        print('\n'.join(tail))
    return 0 if j['status'] == 'finished' else 3


def cmd_log(jid, lines=40):
    d = load(); j = d.get(jid)
    if not j or not os.path.exists(j['log']):
        print('没有日志'); return 2
    print('\n'.join(open(j['log'], errors='ignore').read().splitlines()[-lines:]))
    return 0


def cmd_stop(jid):
    d = load(); j = d.get(jid)
    if not j:
        print('没有这个 job'); return 2
    try:
        os.killpg(os.getpgid(j['pid']), signal.SIGTERM)
        print('已终止进程组')
    except Exception:
        try:
            os.kill(j['pid'], signal.SIGTERM); print('已终止进程')
        except Exception as e:
            print('终止失败:', e)
    j['status'] = 'killed'; save(d)
    return 0


def cmd_prune():
    d = refresh(load())
    keep = {k: v for k, v in d.items() if v['status'] == 'running'}
    save(keep)
    print(f'清理 {len(d)-len(keep)} 条已结束记录，保留 {len(keep)} 条运行中')
    return 0


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return 2
    c = a[0]
    if c == 'start':
        if '--' not in a or len(a) < 4:
            print('用法: video_job.py start --name X -- <cmd...>'); return 2
        i = a.index('--')
        head, cmd = a[1:i], a[i+1:]
        name = 'job'
        if '--name' in head:
            name = head[head.index('--name') + 1]
        return start(name, cmd)
    if c == 'list': return cmd_list()
    if c == 'status' and len(a) > 1: return cmd_status(a[1])
    if c == 'log' and len(a) > 1:
        n = 40
        if '--lines' in a: n = int(a[a.index('--lines') + 1])
        return cmd_log(a[1], n)
    if c == 'stop' and len(a) > 1: return cmd_stop(a[1])
    if c == 'prune': return cmd_prune()
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main())
