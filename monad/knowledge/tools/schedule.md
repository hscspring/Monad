# schedule — 定时任务与监控

MONAD 支持通过 `python_exec` 创建定时任务和监控任务。以下函数已预注入到执行环境中。

## schedule_task(task, schedule, notify="auto", name=None)

创建一个定时执行的任务。

**参数：**
- `task`：任务描述（和你直接给 MONAD 的指令一样）
- `schedule`：调度表达式
  - `"daily 08:00"` — 每天 8 点
  - `"hourly"` — 每小时
  - `"every 30m"` — 每 30 分钟
  - `"every 2h"` — 每 2 小时
  - `"weekly mon 09:00"` — 每周一 9 点
  - `"monthly 1 10:00"` — 每月 1 号 10 点
- `notify`：通知方式 — `"auto"`（跟随启动模式）、`"web"`、`"feishu"`、`"cli"`、`"desktop"`
- `name`：任务名称（可选，自动生成）

**示例：**
```python
schedule_task("生成今日简报并推送给我", "daily 08:00", notify="feishu", name="daily_briefing")
```

## monitor_condition(condition_code, task, interval_minutes=60, notify="auto", name=None)

创建一个监控任务，当条件满足时触发。

**参数：**
- `condition_code`：Python 代码字符串，返回 True 表示条件满足
- `task`：条件触发后执行的任务描述
- `interval_minutes`：检查间隔（分钟，默认 60）
- `notify`：通知方式
- `name`：任务名称（可选）

**示例：**
```python
monitor_condition(
    'import json; r = web_fetch(url="https://api.example.com/price"); float(json.loads(r)["price"]) < 100',
    "价格已低于 100，请查询详情并通知我",
    interval_minutes=30,
    name="price_alert"
)
```

## list_schedules()

列出所有已注册的定时/监控任务及其状态。

```python
print(list_schedules())
```

## cancel_schedule(name)

取消（删除）一个定时任务。

```python
cancel_schedule("daily_briefing")
```
