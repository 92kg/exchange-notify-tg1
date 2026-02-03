# 加密货币情绪监控系统 v3.0

多交易所、多币种支持的加密货币情绪量化监控系统

## 功能特性

### 核心功能
- ✅ 多维度情绪量化（恐慌指数、资金费率、多空比）
- ✅ 情绪拐点确认（防止过早入场）
- ✅ 资金费率分位数（自适应牛熊市）
- ✅ 信号共振检测（多币种验证）
- ✅ Telegram实时推送
- ✅ SQLite3数据持久化

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

telegram:
  bot_token: "你的Bot_Token"
  chat_id: "你的Chat_ID"
  enabled: true
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

### Q: OKX被封了怎么办？

修改配置文件切换到Binance即可。

## 技术栈

- Python 3.8+
- SQLite3
- requests
- PyYAML

## 作者

Claude (Anthropic AI Assistant)

## 许可证

MIT License

## 更新日志

### v3.0.0 (2025-02-02)
- ✨ 模块化架构重构
- ✨ 多交易所支持
- ✨ 配置文件管理
- ✨ 灵活币种配置
- ✨ 完善的日志系统

### v2.1.0
- ✨ 历史数据回测
- ✨ 参数优化

### v2.0.0
- ✨ SQLite3持久化
- ✨ 情绪拐点确认

### v1.5.0
- ✨ 资金费率分位数
- ✨ 信号共振检测

### v1.0.0
- 🎉 初始版本