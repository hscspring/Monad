# Protocol: Missing Dependency

当 MONAD 执行代码时遇到 ImportError 或 ModuleNotFoundError，按以下流程处理：

## 步骤

1. **识别缺失模块**：从错误信息中提取模块名（如 `No module named 'cv2'`）
2. **尝试直接安装**：`pip install <module_name>`
3. **如果安装失败或模块名 ≠ 包名**（常见映射见下方）：
   - 用 web_fetch 搜索：`web_fetch url="https://www.bing.com/search?q=python+install+<module_name>+pip"`
   - 从搜索结果找到正确的包名
   - 重新 `pip install <correct_package_name>`
4. **如果是系统级依赖**（如 ffmpeg, poppler, tesseract）：
   - macOS: `shell: brew install <package>`
   - Linux: `shell: apt-get install <package>` 或 `yum install <package>`
   - 不确定时，先搜索安装方法
5. **如果仍然失败**：向用户报告详细错误信息，说明已尝试的解决方案

## 常见 Python 模块名 → pip 包名映射

| 模块名 | pip 包名 |
|--------|----------|
| cv2 | opencv-python |
| PIL | Pillow |
| sklearn | scikit-learn |
| bs4 | beautifulsoup4 |
| yaml | pyyaml |
| dotenv | python-dotenv |
| gi | PyGObject |

## 示例

```
错误: No module named 'cv2'
→ thought: cv2 是 OpenCV 的 Python 模块，对应的 pip 包名是 opencv-python
→ action: shell "pip install opencv-python"
→ 重试原始代码
```

```
错误: pip install xxx 失败
→ thought: 安装失败，我需要搜索正确的安装方法
→ action: web_fetch "https://www.bing.com/search?q=pip+install+xxx+error"
→ 根据搜索结果修正安装命令
→ 重试
```
