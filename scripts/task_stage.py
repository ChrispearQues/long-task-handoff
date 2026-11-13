#!/usr/bin/env python3
"""分阶段执行大任务：把计划写进状态文件，回复丢了也能接上。

  task_stage.py start "<任务名>" --stages "阶段一|阶段二|阶段三"
  task_stage.py next                      # 当前阶段完成 → 进下一阶段，打印该说的话
  task_stage.py status                    # 看进度（新会话/回复丢失后先跑这个）
  task_stage.py done | abort

设计要点：每阶段目标 ≤4 分钟，结束立刻回复并请用户说「继续」续窗口。
"""
import json, os, sys, time
from datetime import datetime

STATE = os.path.expanduser(os.environ.get('TASK_STAGE_STATE', '~/.openclaw/state/task_stages.json'))


def load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def save(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(d, open(STATE, 'w'), ensure_ascii=False, indent=1)


def active(d):
    for k, v in d.items():
        if v.get('status') == 'running':
            return k, v
    return None, None


def start(name, stages):
    d = load()
    key = time.strftime('%m%d-%H%M')
    d[key] = {'name': name, 'stages': stages, 'idx': 0, 'status': 'running',
              'started': datetime.now().strftime('%Y-%m-%d %H:%M')}
    save(d)
    print(f'任务已登记 [{key}] {name}')
    for i, s in enumerate(stages, 1):
        print(f'  {i}. {s}')
    print(f'当前阶段：1/{len(stages)} — {stages[0]}')
    print('（每阶段控制在 4 分钟内，结束跑 task_stage.py next）')


def next_():
    d = load()
    k, v = active(d)
    if not k:
        print('没有进行中的任务；用 start 开一个'); return 2
    n = len(v['stages'])
    if v['idx'] + 1 >= n:
        v['status'] = 'done'; save(d)
        print(f'✅ 全部 {n} 个阶段完成：{v["name"]}')
        print('回复用户：整件事做完了，这是最终结果。')
        return 0
    v['idx'] += 1; save(d)
    i = v['idx']
    print(f'阶段 {i}/{n} 完成 → 下一阶段 {i+1}/{n}：{v["stages"][i]}')
    print('回复模板：')
    print(f'  「阶段 {i}/{n} 好了：<一句话结果>。还有 {n-i} 段，回我一句「继续」我接着做。」')
    return 0


def status():
    d = load()
    k, v = active(d)
    if not v:
        print('没有进行中的任务')
        done = [ (kk,vv) for kk,vv in d.items() if vv.get('status')=='done' ]
        if done:
            kk, vv = done[-1]
            print(f'最近完成：{vv["name"]}（{len(vv["stages"])} 阶段，{vv["started"]}）')
        return 0
    n = len(v['stages'])
    print(f'[{k}] {v["name"]}  {v["idx"]+1}/{n}  开始于 {v["started"]}')
    for i, s in enumerate(v['stages'], 1):
        mark = '→' if i - 1 == v['idx'] else ('✓' if i - 1 < v['idx'] else ' ')
        print(f'  {mark} {i}. {s}')
    return 0


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return 2
    c = a[0]
    if c == 'start':
        name = a[1] if len(a) > 1 else '未命名任务'
        stages = None
        if '--stages' in a:
            stages = [s.strip() for s in a[a.index('--stages') + 1].split('|') if s.strip()]
        if not stages:
            print('需要 --stages "阶段一|阶段二|阶段三"'); return 2
        return start(name, stages)
    if c == 'next': return next_()
    if c == 'status': return status()
    if c in ('done', 'abort'):
        d = load(); k, v = active(d)
        if not v:
            print('没有进行中的任务'); return 2
        v['status'] = 'done' if c == 'done' else 'aborted'; save(d)
        print(f'{"完成" if c=="done" else "中止"}：{v["name"]}'); return 0
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main())
