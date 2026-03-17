# Protocol: PDF 生成

## 首选方案：使用 markdown_to_pdf 技能

当需要生成 PDF 报告时，**优先使用 `markdown_to_pdf` 技能**，不要手写 reportlab 代码。

### 正确流程

1. 用 `python_exec` 生成 Markdown 格式的报告内容（字符串）
2. 调用 `markdown_to_pdf` 技能，传入 `content` 参数

```json
{"type": "action", "capability": "markdown_to_pdf", "params": {"content": "# 报告标题\n\n## 第一章\n\n正文内容...", "output_filename": "report.pdf"}}
```

### markdown_to_pdf 支持的格式

- 标题：`#`、`##`、`###`
- 粗体：`**文字**`
- 斜体：`*文字*`
- 行内代码：`` `code` ``
- 列表：`- item` 或 `* item`
- 分隔线：`---`
- 段落：空行分隔

### 典型用法

先用 python_exec 把分析结果组织成 markdown 字符串，保存到变量或文件：

```python
report = """# 分析报告

## 概要

这是报告正文...

## 详细分析

- 要点一
- 要点二

---

*报告由 MONAD 生成*
"""
# 写到文件供 markdown_to_pdf 读取
with open(os.path.join(MONAD_OUTPUT_DIR, "report.md"), "w") as f:
    f.write(report)
print(report)
```

然后调用技能：

```json
{"type": "action", "capability": "markdown_to_pdf", "params": {"file_path": "~/.monad/output/report.md", "output_filename": "report.pdf"}}
```

## 仅当 markdown_to_pdf 不可用时：手写 reportlab

如果技能不可用，才考虑手写代码。关键规则：

- 使用 `reportlab` + `UnicodeCIDFont('STSong-Light')` 确保中文显示
- **不要用 fpdf**（不支持中文）、**不要用 weasyprint**（依赖系统 C 库）
- **不要用 STHeiti-Regular**（reportlab 不支持），只用 `STSong-Light`
- 长代码必须先写到 `.py` 文件再用 shell 执行（python_exec 有 80 行限制）
