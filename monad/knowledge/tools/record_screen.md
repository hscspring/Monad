# Screen Recording (start_recording + stop_recording)

Screen recording is split into two atomic skills for composability.

## start_recording

Start background screen recording. Returns immediately (non-blocking).

```python
start_recording()                                    # default output to ~/.monad/output/
start_recording(output_path="/tmp/demo.mkv")         # custom path
```

| Parameter | Description |
|-----------|-------------|
| output_path | Optional. Output file path (MKV format during recording). Default: `~/.monad/output/recording_<timestamp>.mkv` |

Records to MKV via ffmpeg AVFoundation. State persisted to `~/.monad/cache/recording_state.json`.

## stop_recording

Stop the current recording, transcode to MP4, return the file path and download URL.

```python
stop_recording()
```

Returns: file path + `http://localhost:8000/output/<filename>.mp4` download link.

Internally sends SIGTERM to the ffmpeg process, then transcodes MKV → MP4 with `+faststart` (guarantees valid moov atom and browser-playable file).

## Typical Workflow

```
1. start_recording()                    # begin recording
2. ... perform other tasks ...          # send messages, browse, etc.
3. stop_recording()                     # stop recording, get MP4 path + URL
```

## Notes

- Requires screen recording permission: System Preferences → Privacy & Security → Screen Recording → enable Terminal/Python
- Records full screen (Retina resolution) with system audio
- Requires ffmpeg (`brew install ffmpeg`)
- Recording runs as a background process; other skills can execute concurrently
