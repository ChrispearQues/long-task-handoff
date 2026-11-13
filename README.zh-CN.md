# long-task-handoff（长任务交接）

> [English](README.md) | **中文**

一个给 [OpenClaw](https://openclaw.ai) 用的技能：让长任务不再堵住对话。

聊天平台把**回复权限**绑在**用户那条消息**上。QQ 的规则是：一条入站消息允许 5 分钟内回 5 条。一个跑 10 分钟的回合，答完了也发不出去，而接口照样返回 `200 OK`——活干完了、用户什么都没收到，双方都以为机器人卡死。

这个技能把这层耦合拆开：长活移出回合，走三条车道；agent 始终保持秒回；完成时用主动消息播报。

```
用户 ──> 接频道的 agent  ── 短活（约 2 分钟内）：本回合直接答
              │
              └─ 长活 ──> 任务卡落盘（~/.openclaw/jobs）
                              │
                     worker（隔离会话，cron 轮询）
                              │  执行、写产物
                              └─ 播报「任务完成：<标题> — <一行>」
                                              │
                                   用户回一个字 ──> agent 发详情/附件
```

## 三条车道

| 车道 | 用来做什么 | 工具 | token 成本 |
|---|---|---|---|
| 进程 | 渲染、转码、批量 OCR | `scripts/video_job.py` | 无 |
| Agent | 需要模型思考的活 | `scripts/jobq.py` + worker cron | 有 |
| 分阶段 | 必须跨多轮、中间要用户确认的活 | `scripts/task_stage.py` | 有 |

## 文件说明

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 操作说明：车道、硬规则、踩坑、边界 |
| `scripts/jobq.py` | 持久任务队列：提交、原子领取、完成、失败、回收 |
| `scripts/video_job.py` | 脱离会话的进程管理（`setsid`）：start/list/status/log/stop |
| `scripts/video_job_watch.py` | 给 cron 用的一次性「哪些跑完了」报告 |
| `scripts/task_stage.py` | 分阶段协议，带可恢复状态 |
| `examples/cron-worker.md` | 可直接抄的 worker cron 配置 |

## 快速开始

```bash
# 1) 提交任务，而不是在回合里硬干
python3 scripts/jobq.py submit --title "周报" \
  --task "读 notes/*.md，产出一页纸摘要到 OUT/summary.md" \
  --out /tmp/report

# 2) 注册 worker cron（见 examples/cron-worker.md），每 5 分钟轮询一次

# 3) 之后取结果
python3 scripts/jobq.py show <id>
```

纯 CPU 的活可以不用队列：

```bash
python3 scripts/video_job.py start --name ep12 -- ffmpeg -y -i in.mp4 -c:v libx264 out.mp4
python3 scripts/video_job.py list
```

## 五条来自实战的结论

每一条都是踩坑踩出来的，文档里查不到：

1. **被动窗口锚定在用户那条消息上**，机器人自己发消息**不能续期**。第 4 分钟回一句「还在做」，只是花掉 5 条里的一条，5 分整照样过期。
2. **隔离会话的投递是主动消息**，不受该窗口限制——所以 worker 能跑 15 分钟还把结果推回来。
3. **一次工具报错会吞掉整条回复**。一个没加 `-p` 的 `mkdir` 碰巧失败，就把已经完成的任务标记为失败，播报被丢弃。worker 里每条命令都必须容错。
4. **主动投递带不了附件**。播报只能是文字，附件必须由接频道的会话普通回复发送。
5. **worker 的旁白会漏进聊天**。它说一句「我先去查任务队列」，这句话就会被当成答复投递给用户。worker 必须闭嘴，只在有结果时说话。

## 设计要点

- **原子领取**：先把状态改成 `running` 再输出任务内容，两个 worker 不会抢同一个任务。
- **默认持久化**：队列与任务正文都落盘，gateway 重启不丢。
- **进程隔离**：`video_job.py` 用 `setsid` 启动，渲染不受会话结束、重启、断线影响。
- **便宜轮询**：worker 大多数轮次只是「没任务」，用小上下文跑。
- **失败可见**：`failureAlert` 加 `reap`，坏掉的 worker 不会和闲置的 worker 长得一样。

## 边界（明确不做的事）

- **不保证送达**：平台侧投递是尽力而为，只有用户回一句才算证实。
- **不是加速器**：目标是「不阻塞」，不是「编码更快」。
- **不替代调度器**：周期性任务仍用 cron。

## 环境要求

- Python 3.9+（只用标准库）
- 提交的命令若用到 `ffmpeg`，需在 PATH 中
- OpenClaw 提供 cron 与隔离会话

## 许可

MIT
