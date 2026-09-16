# Contributing

感谢你改进 Switch Tracker。提交改动即表示你有权按项目的 MIT License 提供这些内容。

## 开始开发

1. Fork 仓库并创建聚焦单一问题的分支。
2. 创建虚拟环境并安装 `requirements-dev.txt`。
3. 不要使用真实令牌或个人数据库编写测试；请使用临时目录和合成数据。
4. 修改行为时补充或更新回归测试。
5. 提交前运行 `ruff check .`、`pytest` 和 `node --check script.js`。

## 提交 Pull Request

- 清楚说明问题、解决方案和验证方式。
- 保持改动聚焦，避免同时进行无关格式化。
- UI 改动请附前后截图。
- 不要提交 `config/`、数据库、日志、原始 API 响应或其他个人数据。

## 报告问题

普通错误可以创建 Issue，并提供 Python 版本、操作系统、复现步骤和已脱敏的日志。涉及令牌泄露、任意文件读取等安全问题时，请遵循 [SECURITY.md](SECURITY.md)，不要公开披露。
