# record_screen skill

录制屏幕为 mp4 视频（后台运行，不阻塞其他任务）。

## 用法

```python
record_screen(action="start")                           # 开始录制，立即返回
record_screen(action="start", output_path="/tmp/demo.mp4")  # 指定输出路径
record_screen(action="status")                          # 查询录制状态
record_screen(action="stop")                            # 停止录制，返回文件路径
```

## 参数

| 参数 | 说明 |
|------|------|
| action | 必填：start / stop / status |
| output_path | 可选（仅 start 有效），默认 ~/.monad/output/recording_<timestamp>.mp4 |

## 典型工作流

```
1. record_screen(action="start")          # 开始录屏
2. ... 执行其他任务（发消息、抓网页等）...
3. record_screen(action="stop")           # 停止录屏，得到 mp4 路径
```

## 注意事项

- 首次使用需在系统偏好设置 → 隐私与安全性 → 屏幕录制 → 勾选终端/Python 授权
- 录制全屏（2880x1800 Retina），含系统音频
- 基于 ffmpeg，需已安装（brew install ffmpeg）
- 录制为后台进程，不影响其他 skill 并发执行
