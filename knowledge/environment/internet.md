# Environment: Internet

Internet access is required for:
- 搜索信息（通过搜索引擎）
- API calls (weather, data services, etc.)
- Online data retrieval

## 工具选择决策树

```
需要互联网信息？
├── 需要网页内容 → web_fetch（首选！）
│   ├── 普通网页 → mode="fast"（默认）
│   ├── 反爬/Cloudflare → mode="stealth"
│   └── JS 渲染/SPA → mode="browser"
├── 需要调用 API → python_exec（写代码调用）
└── 需要安装库 → shell（pip install）
```

## web_fetch — 互联网感知（推荐）

直接获取网页内容，无需写代码：

### 搜索引擎（最重要的信息获取方式）

Bing 搜索（推荐，无需 API key）：
```json
{"capability": "web_fetch", "params": {"url": "https://www.bing.com/search?q=搜索关键词"}}
```

百度搜索（中文信息推荐）：
```json
{"capability": "web_fetch", "params": {"url": "https://www.baidu.com/s?wd=搜索关键词"}}
```

### 精确提取内容
```json
{"capability": "web_fetch", "params": {"url": "https://example.com", "selector": ".article-content"}}
```

### 反爬绕过
```json
{"capability": "web_fetch", "params": {"url": "https://protected.com", "mode": "stealth"}}
```

### 动态页面
```json
{"capability": "web_fetch", "params": {"url": "https://spa.com", "mode": "browser"}}
```

## python_exec — 复杂数据获取与处理

当需要调用 API 或对数据做复杂处理时，用 python_exec：

### 天气 API
```python
import requests
url = "https://api.open-meteo.com/v1/forecast"
params = {"latitude": 30.25, "longitude": 120.17, "current_weather": True}
resp = requests.get(url, params=params, timeout=10)
print(resp.json())
```

## 常用 API

- Weather: Open-Meteo (free, no API key) — `https://api.open-meteo.com/v1/forecast`
- Geocoding: Open-Meteo — `https://geocoding-api.open-meteo.com/v1/search`
