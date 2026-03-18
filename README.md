# 加密货币情绪监控系统 v3.5.0

多交易所、多币种支持的加密货币情绪量化监控系统。基于情绪驱动的 V8 趋势追踪策略，内置动态止损与加仓逻辑。

## 功能特性

### 核心功能
- ✅ **V8 趋势策略**：基于 2000天 回测验证 (总回报 +3357%, 胜率 56%)
- ✅ **自动风控系统**：支持 -15% 动态止损 (Trailing Stop) + 自动平仓
- ✅ **盈利加仓 (Pyramiding)**：趋势确认后自动提示加仓，优化通知逻辑避免重复提醒
- ✅ **智能通知**：Telegram 推送包含明确的"建议操作" (买入/止损价计算)
- ✅ **隐私安全**：数据与策略完全本地运行

### 策略逻辑
- **买入**：恐慌指数 < 25 (战略) + 价格站上 MA7/MA30 (战术)
- **卖出**：触及动态止损线 (-15%) 自动离场 (情绪卖出信号在回测中表现不佳，已禁用)
- **加仓**：现有持仓浮盈 > 5% 且出现新买入信号时触发

### 交易所支持
- ✅ OKX (支持行情 + 自动交易)
- ✅ Binance (仅支持行情)

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置系统
编辑 `config.yaml`（参考 `config.sample.yaml`）:

```yaml
# 自动交易 (推荐开启)
auto_close: true

# 风控配置
risk:
  stop_loss_type: "trailing"
  stop_loss_pct: -15

# Telegram 通知
telegram:
  bot_token: "你的Bot_Token"
  chat_id: "你的Chat_ID"
  enabled: true
```

### 3. 运行系统
**Windows (推荐):**
双击 `start.bat` 一键启动（自动创建虚拟环境并安装依赖）。

**命令行:**
```bash
python main.py
```

## 常用命令
```bash
# 查看回测统计与过拟合预警
python main.py --stats

# 查看历史信号 (SQLite)
sqlite3 crypto_sentiment_v3.db "SELECT * FROM signals ORDER BY timestamp DESC LIMIT 10;"
```

## 项目结构
```
encrypt_monitor/
├── config.yaml              # 配置文件
├── main.py                  # 主程序入口
├── exchanges/               # 交易所 API 实现
├── analyzers/               # 情绪、信号、持仓分析模块
├── database/                # SQLite3 持久化管理
├── notifiers/               # 消息通知模块 (Telegram)
└── utils/                   # 辅助工具函数
```

## 常见问题
- **如何添加新币种？** 修改 `config.yaml` 的 `coins` 列表后重启即可。
- **如何避免过拟合？** 使用 `--stats` 命令监控风险评级，减少启用条件。
- **数据保存在哪？** 全部记录在 `crypto_sentiment_v3.db` 中。

## 更新日志

### v3.5.0 (2026-03-18)
- 🚀 **通知优化**：修复已有持仓时重复发送下单提醒的问题
- 🧹 **项目清理**：移除冗余测试脚本与临时日志，精简代码库
- 📝 **文档更新**：重构 README，统一版本号与功能描述

### v3.4.0 (2026-02-06)
- 🎯 **策略定型**：确定 V8 趋势买入 + 动态止损作为主力逻辑
- ❌ **移除噪音**：正式禁用情绪卖出信号（回测胜率过低）

### v3.2.0 (2026-02-03)
- 🛡️ **风控强化**：添加策略复杂度评估与过拟合风险分级

---
**免责声明**：本系统仅供量化研究使用，不构成投资建议。加密货币投资具有高风险，请谨慎操作。