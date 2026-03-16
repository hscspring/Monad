# Protocol: PDF 生成（中文支持）

当需要生成包含中文的 PDF 文件时，按以下流程处理：

## 推荐方案：reportlab + CJK 字体

reportlab 内置 CJK 字体支持，无需额外安装系统依赖。

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 注册中文字体（reportlab 内置，无需额外文件）
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

# 创建中文样式
cn_style = ParagraphStyle(
    'Chinese', fontName='STSong-Light', fontSize=12, leading=18
)
cn_title = ParagraphStyle(
    'ChineseTitle', fontName='STSong-Light', fontSize=18,
    leading=24, spaceAfter=12, alignment=1  # 居中
)
cn_heading = ParagraphStyle(
    'ChineseHeading', fontName='STSong-Light', fontSize=14,
    leading=20, spaceAfter=10, spaceBefore=10
)
```

## 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| fpdf 中文乱码 | fpdf 1.x 仅支持 Latin-1 | 改用 reportlab |
| weasyprint import 失败 | 缺少 pango/cairo 系统库 | 改用 reportlab（纯 Python） |
| reportlab 中文显示为方框 | 未注册 CJK 字体 | 用 UnicodeCIDFont('STSong-Light') |
| reportlab 未安装 | 缺少依赖 | pip install reportlab |

## 关键规则

- **不要用 fpdf**：不支持中文
- **不要用 weasyprint**：依赖系统 C 库，安装复杂
- **reportlab 是首选**：纯 Python，内置 CJK 字体，pip install 即可
- 所有 Paragraph 的 fontName 都必须设为 CJK 字体，包括标题、正文、列表项
- **长报告必须先写文件再执行**：PDF 生成代码通常超过 80 行，直接放在 python_exec 的 code 字段会导致 JSON 输出被截断。正确做法：先用 python_exec 把完整的 .py 脚本 write 到文件，再用 shell `python /path/to/script.py` 执行
