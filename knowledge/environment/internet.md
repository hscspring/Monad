# Environment: Internet

Internet access is required for:
- 搜索信息（通过搜索引擎）
- API calls (weather, data services, etc.)
- Online data retrieval

## 搜索引擎（最重要的信息获取方式）

需要搜索任何信息时，优先使用搜索引擎，不要猜测具体网站：

### Bing 搜索（推荐，无需 API key）
```python
import requests
from bs4 import BeautifulSoup

url = "https://www.bing.com/search"
params = {"q": "你的搜索关键词"}
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
resp = requests.get(url, params=params, headers=headers, timeout=10)
resp.encoding = resp.apparent_encoding
soup = BeautifulSoup(resp.text, 'html.parser')
for item in soup.select('li.b_algo h2 a'):
    print(item.get_text(strip=True))
```

### 百度搜索（中文信息推荐）
```python
url = "https://www.baidu.com/s"
params = {"wd": "你的搜索关键词"}
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
resp = requests.get(url, params=params, headers=headers, timeout=10)
resp.encoding = resp.apparent_encoding
```

## 中文网页抓取注意事项

抓取中文网站时必须处理编码：
```python
resp = requests.get(url, headers=headers, timeout=10)
resp.encoding = resp.apparent_encoding  # 自动检测编码
```

## 常用 API

- Weather: Open-Meteo (free, no API key) — `https://api.open-meteo.com/v1/forecast`
- Geocoding: Open-Meteo — `https://geocoding-api.open-meteo.com/v1/search`
