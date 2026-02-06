# 加密货币情绪监控系统 v3.4

多交易所、多币种支持的加密货币情绪量化监控系统

## 功能特性

### 核心功能
- ✅ **V8 趋势策略**：回测胜率 57%，30天收益 +5.28%
- ✅ 技术分析（MA7/MA30 趋势确认）
- ✅ 止损机制（默认 -15%）
- ✅ 价格数据缓存
- ✅ 恐慌指数监控
- ✅ Telegram 实时推送
- ✅ SQLite3 数据持久化
- ✅ 5.5年历史数据回测验证

> ⚠️ 情绪卖出信号已禁用（回测正确率仅38%）

### 交易所支持
- ✅ OKX
- ✅ Binance
- ⏳ Bybit (规划中)

### 币种支持
- ✅ BTC / ETH (默认启用)
- ✅ 任意山寨币（配置文件添加）

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置系统

编辑 `config.yaml`:
```yaml
exchange:
  name: "okx"  # 选择交易所

coins:
  - symbol: "BTC"
    enabled: true
  - symbol: "ETH"
    enabled: true

# 策略配置
strategy:
  mode: "trend"              # 策略模式: trend(推荐) / fear_buy
  use_fear_greed: true       # 使用恐慌指数
  use_funding_percentile: true
  use_reversal: true
  use_sell_signal: false     # 禁用卖出信号

# 趋势策略参数
trend_strategy:
  ma_short: 7                # 短期均线
  ma_long: 30                # 长期均线
  max_fg_value: 70           # 避免追高

telegram:
  bot_token: "你的Bot_Token"
  chat_id: "你的Chat_ID"
  enabled: true
```

### 3. 运行系统

**Windows (推荐):**
双击 `start.bat` 即可一键启动（自动创建虚拟环境并安装依赖）。

**命令行:**
```bash
# 启动监控系统
python main.py

# 查看回测统计
python backtest.py
```

## 策略配置指南

详细说明请查看 [STRATEGY_GUIDE.md](STRATEGY_GUIDE.md)

### 条件重要性排序

1. ⭐⭐⭐⭐⭐ **恐慌指数** - 核心，禁用后系统无法工作
2. ⭐⭐⭐⭐⭐ **拐点确认** - 强烈推荐，防止过早入场
3. ⭐⭐⭐ **资金费率分位数** - 可选，验证信号强度
4. ⭐⭐ **多空比** - 谨慎使用，容易被操纵
5. ⭐⭐ **共振检测** - 谨慎使用，币种少时无效

### 推荐配置

**保守策略（新手）**：
```yaml
strategy:
  use_fear_greed: true
  use_reversal: true
  其他: false
```

**平衡策略（推荐）**：
```yaml
strategy:
  use_fear_greed: true
  use_funding_percentile: true
  use_reversal: true
  其他: false
```

### 3. 运行系统
```bash
python main.py
```

## 添加新币种

只需修改 `config.yaml`:
```yaml
coins:
  - symbol: "SOL"
    enabled: true
    weight: 0.3
  - symbol: "AVAX"
    enabled: true
    weight: 0.2
```

保存后重启系统即可！

## 切换交易所

修改 `config.yaml`:
```yaml
exchange:
  name: "binance"  # 从okx切换到binance
```

## 部署方案

### 本地运行
```bash
# 前台运行
python main.py

# 后台运行
screen -S crypto_v3
python main.py
# Ctrl+A, D 分离
```

### 服务器部署

创建systemd服务:
```bash
sudo nano /etc/systemd/system/crypto-monitor-v3.service
```
```ini
[Unit]
Description=Crypto Sentiment Monitor v3.0
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/crypto_monitor_v3
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl start crypto-monitor-v3
sudo systemctl enable crypto-monitor-v3
sudo systemctl status crypto-monitor-v3
```

## 项目结构
```
crypto_monitor_v3/
├── config.yaml              # 配置文件
├── main.py                  # 主程序
├── exchanges/               # 交易所模块
│   ├── base.py             # 基类
│   ├── okx.py              # OKX实现
│   └── binance.py          # Binance实现
├── analyzers/               # 分析器
│   ├── sentiment.py        # 情绪分析
│   └── signal.py           # 信号生成
├── database/                # 数据库
│   └── manager.py          # 数据管理
├── notifiers/               # 通知
│   └── telegram.py         # Telegram
└── utils/                   # 工具
    └── helpers.py          # 辅助函数
```

## 常见问题

### Q: 如何添加新交易所？

1. 在 `exchanges/` 目录创建新文件
2. 继承 `ExchangeBase` 类
3. 实现所有抽象方法
4. 在 `exchanges/__init__.py` 注册

### Q: 数据保存在哪里？

所有数据保存在 `crypto_sentiment_v3.db` SQLite数据库中。

### Q: 如何查看历史信号？
```bash
sqlite3 crypto_sentiment_v3.db
SELECT * FROM signals ORDER BY timestamp DESC LIMIT 10;
```

### Q: 如何查看回测统计信息？
```bash
sqlite3 crypto_sentiment_v3.db
SELECT signal_type, COUNT(*) as total, 
       AVG(return_7d) as avg_return_7d
FROM signals 
WHERE return_7d IS NOT NULL 
GROUP BY signal_type;
```

### Q: OKX被封了怎么办？

修改配置文件切换到Binance即可。

### Q: 回测功能如何工作？

系统会自动检查所有未回测的历史信号，调用交易所API获取N天后的价格，自动计算并填充收益率数据。可在 `config.yaml` 中配置回测天数。

### Q: 如何避免过度拟合？

1. 使用 `strategy` 配置关闭不必要的条件
2. 使用 `python main.py --stats` 查看过拟合警告
3. 保持样本量至少30个信号
4. 胜率不应超过80%（否则可能过拟合）

### Q: 如何优化策略复杂度？

```
最保守策略（低风险）:
strategy:
  use_fear_greed: true
  use_funding_percentile: false
  use_longshort: false
  use_reversal: true
  use_resonance: false

中等策略（平衡）:
strategy:
  use_fear_greed: true
  use_funding_percentile: true
  use_longshort: false
  use_reversal: true
  use_resonance: false
```

## 技术栈

- Python 3.8+
- SQLite3
- requests
- PyYAML

## 作者

Claude (Anthropic AI Assistant)

## 版本

v3.2.0 (2026-02-03)

## 许可证

MIT License

## 更新日志

### v3.4.0 (2026-02-06)
- 🎯 **确定最终策略**：V8 趋势买入 + 止损
- ❌ 禁用情绪卖出信号（回测正确率仅38%）
- 📊 添加止损机制和最大回撤分析
- 📝 更新策略指南文档

### v3.3.0 (2026-02-06)
- 🚀 **新增趋势策略 (V8)**：回测胜率 57%，30天收益 +5.28%
- 📊 新增策略模式选择：`strategy.mode: "trend"` / `"fear_buy"`
- 📁 新增价格数据缓存：减少 API 调用
- 📈 新增技术分析模块：`analyzers/trend.py`
- 📝 更新策略指南文档

### v3.2.0 (2026-02-03)
- 🛡️ 添加策略复杂度评估和风险预警
- 📊 优化统计信息展示，新增过拟合警告
- 🎯 新增 `python main.py --stats` 查看回测统计
- 🔧 修复买卖信号不对称问题
- 📝 完善策略配置文档

### v3.1.0 (2026-02-03)
- ✨ 历史信号自动回测功能
- ✨ API超时时间优化（10s→30s）
- ✨ 添加请求重试机制（最多3次）

### v3.0.0 (2025-02-02)
- ✨ 模块化架构重构
- ✨ 多交易所支持
- ✨ 配置文件管理
- ✨ 灵活币种配置
- ✨ 完善的日志系统

### v2.0.0
- ✨ SQLite3持久化
- ✨ 情绪拐点确认

### v1.5.0
- ✨ 资金费率分位数
- ✨ 信号共振检测

### v1.0.0
- 🎉 初始版本