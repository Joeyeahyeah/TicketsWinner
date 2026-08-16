# TicketsWinner 开发指南

本指南为编码代理（coding agent）在更新本仓库时提供上下文。

> ⚠️ **项目性质**：本仓库为**个人学习与自用**项目，仅用于给自己抢票、学习抓包与安全对抗技术。禁止商用、禁止分发给任何第三方使用。所有与 Damai/WeixinMiniApp 相关的代码仅用于技术研究。

## 项目概览

两个独立的抢票模块，共享少量配置理念：

- **WeixinMiniApp 抢票**（当前主分支 `develop`）— 针对付航脱口秀（caiyicloud 平台）
- **Damai 抢票**（新分支开发）— 针对大麦网演唱会门票，独立目录 `damai/`

## 目录结构

```
TicketsWinner/
├── main.py                  # 顶层入口，调用 weixin_mini_app 模块
├── weixin_mini_app/         # WeixinMiniApp 抢票模块（caiyicloud）
│   ├── __init__.py          # 导出 WeixinMiniAppConfig、grab_tickets
│   ├── config.py            # WeixinMiniAppConfig 配置类（读取 .env）
│   └── grabber.py           # 抢票核心逻辑
├── .env.example             # 环境变量模板
├── requirements.txt
├── README.md
├── AGENTS.md                # 本文件
└── damai/                   # Damai 抢票模块（feature/damai 分支）
    ├── main.py              # 入口：argparse 子命令 login / grab
    ├── config.py            # DamaiConfig（读取 damai/.env，与小程序模块分离）
    ├── .env.example         # damai 环境变量模板
    ├── browser/
    │   ├── browser_manager.py   # Playwright 浏览器管理（加载 storage_state）
    │   ├── login.py             # 扫码登录 + storage_state 持久化
    │   └── stealth.py           # playwright-stealth 反指纹封装
    └── core/
        ├── scheduler.py         # NTP 校时（ntp.aliyun.com）+ 精确等待
        ├── notify.py            # Server酱推送（文本 + 滑块截图）
        └── order.py             # 下单流程（占位，待真机抓包确认后实现）
```

## WeixinMiniApp 模块（weixin_mini_app/）

### 架构要点

- 入口：顶层 `main.py` 调用 `weixin_mini_app.grab_tickets(WeixinMiniAppConfig)`，四步流程：生成 trace-id → 获取预填信息 → 定时等待 → 循环下单
- 配置：`weixin_mini_app/config.py` 的 `WeixinMiniAppConfig` 类从 `.env` 读取，启动时调用 `WeixinMiniAppConfig.validate()` 校验必填项
- 关键 ID：`ticket_item_id` 后缀 `100000008` 对应当前场次票档，**换场次必须抓包重新确认**

### 编码规范

- Python 3，无额外框架，仅 `requests` + `python-dotenv`
- 所有请求必须带 `timeout=WeixinMiniAppConfig.REQUEST_TIMEOUT`
- 日志用 `logging`，不用 `print`（入口处的用户提示除外）
- 票价等可变参数一律走 `WeixinMiniAppConfig`，禁止在代码里硬编码
- 异常处理：网络异常捕获 `requests.RequestException`，解析异常捕获 `(KeyError, ValueError)`，键盘中断 `KeyboardInterrupt` 需优雅退出
- 重试间隔用 `random.uniform(config.RETRY_INTERVAL_MIN, config.RETRY_INTERVAL_MAX)` 随机化，避免固定频率触发风控

### 运行与验证

```bash
pip install -r requirements.txt
cp .env.example .env        # 填入抓包获取的 access_token / WECHAT_APP_ID
python main.py              # 输出「获取预填信息成功」即基础链路正常
```

抓包工具使用 **Whistle**（见 README），抓到的 `access_token`（JWT）**2 小时内有效**，抢票前需重新获取。

## Damai 模块（damai/，新分支开发）

### 开发原则

- 在独立分支开发，目录隔离在 `damai/`，不影响现有小程序模块
- 技术路线采用 **Playwright + 大麦 H5 页面**（由页面内 JS 环境自动生成 mtop 签名，避免逆向阿里签名算法）
- 难点认知：mtop 签名（`x-sign`）本身可逆向，**真正的难点是阿里风控**（设备指纹、行为分析、滑块验证、IP 信誉）

### 目录结构（已落地骨架 + 登录态）

```
damai/
├── main.py                  # 入口：login / grab 子命令
├── browser/
│   ├── browser_manager.py   # Playwright 浏览器管理
│   ├── login.py             # 登录态（扫码 + storage_state 持久化）
│   └── stealth.py           # 反指纹检测（playwright-stealth 封装）
├── core/
│   ├── scheduler.py         # NTP 校时 + 开抢时间精确等待
│   ├── notify.py            # 成功通知（Server酱推送）
│   └── order.py             # 下单流程（占位，待抓包实现）
├── config.py                # 配置（读 damai/.env，与小程序模块分离）
└── .env.example
```

### 当前状态与下一步

- 已完成：配置层、浏览器管理、扫码登录持久化、playwright-stealth 反指纹、NTP 校时定时调度、Server酱通知
- 待实现：`core/order.py` 下单链路 —— 真机/模拟器抓包确认 `mtop.damai.buy.order.create` 版本号（填 `DAMAI_API_VERSION`）与请求体后实现；滑块检测选择器也需抓包后补充
- 运行入口：`python -m damai.main login` / `python -m damai.main grab`（浏览器二进制需先 `playwright install chromium`）

### 关键约定

- 登录态通过 `storage_state` 复用（cookie + localStorage），抢票前一天扫码登录保存，避免抢票时登录排队
- 反指纹必须处理：`navigator.webdriver`、`navigator.plugins`、`window.chrome`、permissions 查询等；优先用 `playwright-stealth`
- 接口 URL（如 `mtop.damai.buy.order.create`）仅作参考起点，**实施时必须真机/模拟器抓包确认当前版本号与请求体结构**，payload 模板化、版本号配置化
- 滑块验证不做自动化绕过：触发后截图推送到手机，人工辅助完成
- 多账号场景：每账号独立浏览器上下文 + 独立住宅代理，各账号启动时间随机偏移 0-200ms
- 时间同步：对接阿里云 NTP（`ntp.aliyun.com`），抢票前校验系统时钟
- 单账号控制 QPS，不盲目并发；随机化请求间隔

### 法律红线（不可违反）

- 仅限本人账号、本人自用
- 不代抢收费、不批量注册、不倒卖门票（刑法第 227 条）
- 不攻击/绕过风控系统做破坏性操作（刑法第 285 条）
- 账号被平台封禁属预期风险，自行承担

## 提交规范

- 使用 conventional commits：`feat`、`fix`、`refactor`、`docs`
- 分支说明：`develop` 维护 WeixinMiniApp 模块；Damai 模块在独立功能分支开发
- 提交前确保 `python main.py`（或对应模块入口）能正常启动，不引入语法/导入错误
- **大改动（重构、重命名、模块拆分、逻辑调整）后必须运行验证**：至少执行 `python main.py` 确认能正常启动（到达「获取预填信息」或配置校验阶段），并检查关键路径无报错；无法本地运行时必须说明原因
- 绝不提交真实 `access_token`、cookie、storage_state 等凭证到仓库（`.env` 与登录态文件必须被 git 忽略）

## 环境变量

| 变量 | 用途 | 必填 |
|---|---|---|
| `WECHAT_APP_ID` | 小程序 AppID（抓包 Referer 中获取） | 是 |
| `ACCESS_TOKEN` | 小程序 access_token（JWT，2 小时有效） | 是 |
| `APP_VERSION` | 小程序版本号（抓包 `ver` 头） | 是 |
| `TICKET_PRICE` / `PRICE_DISPLAY` | 票价与展示文本 | 换场次时更新 |
| `SALE_START_TIME` | 开抢时间 `HH:MM:SS` | 是 |
| `MAX_ATTEMPTS` | 最大请求次数 | 默认 200 |
| `REQUEST_TIMEOUT` | 单请求超时秒数 | 默认 3 |
| `RETRY_INTERVAL_MIN/MAX` | 重试间隔随机范围 | 默认 0.15/0.4 |
