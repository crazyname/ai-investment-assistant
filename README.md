# Personal AI Investment Assistant

这是一个个人 AI 投资/财富管理助手项目。项目当前按时间和用途保留了两个 Streamlit 版本，并加入后台持仓巡检与模拟交易示例。

## 文件结构

- `agent/legacy_gemini_planner.py`：初版应用，只基于 Gemini、手填资产和财经搜索生成投资规划。
- `agent/wealth_advisor_app.py`：当前主应用，包含资产台账、实时行情、AI 投资顾问对话、模型配置和聊天记录管理。
- `agent/portfolio_alert_monitor.py`：后台持仓巡检脚本，可定时生成报告并通过微信模板消息推送。
- `agent/alpaca_paper_trade_demo.py`：Alpaca paper trading 示例脚本，用于模拟盘下单测试。
- `agent/config_utils.py`：读取本地私密配置的工具。
- `agent/private_config.example.txt`：私密配置模板，可复制为 `private_config.txt` 后填写真实信息。
- `agent/start.txt`：主应用启动命令和示例问题。
- `agent/requirements.txt`：项目依赖。

## 本地运行

```powershell
cd D:\enze\Documents\python_project\agent
pip install -r requirements.txt
streamlit run wealth_advisor_app.py
```

## 私密信息

真实的 API Key、微信 OpenID、微信 App Secret、Alpaca Key、个人持仓数据库等都不应上传到 GitHub。

请将 `agent/private_config.example.txt` 复制为 `agent/private_config.txt`，再填入本地密钥。`private_config.txt` 和 `invest_memory.db` 已在 `.gitignore` 中排除。

## 上传策略

已上传的内容只包含代码、依赖、说明文档和无密钥模板。以下内容保留在本地：

- `agent/private_config.txt`
- `agent/invest_memory.db`
- `.env`、`.streamlit/secrets.toml` 等本地环境文件
