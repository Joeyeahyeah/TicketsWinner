# TicketsWinner

TicketsWinner 是个人学习项目，用于抢付航脱口秀门票（WeixinMiniApp 模块），并规划支持大麦网演唱会门票（Damai 模块，开发中）。

> ⚠️ **声明**：本仓库仅用于**个人学习、抓包与安全技术研究及自用抢票**，严禁商用及一切非法用途，请勿分发或提供给任何第三方。本程序仅供学习交流，如非法商用，一切后果自负。

## 项目结构

```
TicketsWinner/
├── main.py                  # 顶层入口
├── weixin_mini_app/         # WeixinMiniApp 抢票模块（付航脱口秀 / caiyicloud）
│   ├── __init__.py          # 导出 WeixinMiniAppConfig、grab_tickets
│   ├── config.py            # 配置类（读取 .env）
│   └── grabber.py           # 抢票核心逻辑
├── .env.example             # 环境变量模板
├── requirements.txt         # 依赖
├── README.md
└── AGENTS.md                # 开发指南（供编码代理参考）
```

### WeixinMiniApp 模块抢票流程

脚本主要分为四步，运行时自动完成：

1. **生成 `front-trace-id`**：时间戳转 base36 + 随机串，无需手动填写
2. **获取抢票预填信息**：自动获取 `preFiledId`、`audienceId`、`seatPlanId`、`showId`、`sessionId`
3. **定时等待**：精确等待到开抢时间
4. **循环抢票**：自动提交订单，成功后提示手动支付，失败自动重试

## 环境部署

### 1. 安装 Python 并配置环境变量

参考：https://blog.csdn.net/2401_83413238/article/details/145422332

### 2. 安装 Whistle 抓包工具

Whistle 是基于 Node.js 的跨平台抓包代理，比 Fiddler 更轻量。

```powershell
npm install -g whistle
w2 start
```

**配置 HTTPS 抓包**（必须，否则抓不到小程序请求）：

1. 浏览器打开 `http://127.0.0.1:8899`
2. 右上角 **HTTPS** → Download RootCA，下载根证书
3. 安装到「本地计算机 → 受信任的根证书颁发机构」
4. 打开 Windows 系统代理：设置 → 网络和 Internet → 代理 → `127.0.0.1:8899`
   > ⚠️ 抓包结束后**务必关闭系统代理**，否则 Whistle 停止后无法上网

### 3. 安装项目依赖

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 快速开始

### 1. 配置 `.env`

```powershell
copy .env.example .env
```

| 变量 | 用途 | 必填 |
|---|---|---|
| `WECHAT_APP_ID` | 小程序 AppID（抓包 Referer 中 `servicewechat.com/<APPID>` 获取） | 是 |
| `ACCESS_TOKEN` | access_token（JWT，**2 小时内有效**，见下方抓包说明） | 是 |
| `APP_VERSION` | 小程序版本号（抓包请求头 `ver` 字段） | 是 |
| `PROVINCE_CITY_ID` / `LOCATION_CITY_ID` | 省份 / 城市 ID | 默认北京 |
| `TICKET_PRICE` / `PRICE_DISPLAY` | 票价，换场次需同步更新 | 否 |
| `SALE_START_TIME` | 开抢时间 `HH:MM:SS` | 是 |
| `MAX_ATTEMPTS` | 最大请求次数（建议 200-300） | 默认 200 |
| `REQUEST_TIMEOUT` | 单请求超时（秒） | 默认 3 |
| `RETRY_INTERVAL_MIN/MAX` | 重试间隔随机范围（秒），随机化以降低风控触发 | 默认 0.15/0.4 |

### 2. 抓取 access_token（抢票前 2 小时内）

1. 启动 Whistle（`w2 start`），打开系统代理 `127.0.0.1:8899`
2. PC 微信进入付航脱口秀小程序，**重新登录账号**，进入「选择场次/座位」页面（不要提交）
3. Whistle 控制台 Network 中搜索 `caiyicloud`，点开任意 GET/POST 请求（注意不是 CONNECT）
4. 在 Request Headers 中复制：
   - `access-token` → 填入 `.env` 的 `ACCESS_TOKEN`
   - `ver` → 填入 `.env` 的 `APP_VERSION`
   - `Referer` 中 `servicewechat.com/wx...` → 填入 `.env` 的 `WECHAT_APP_ID`
5. **关闭系统代理**，恢复正常上网

### 3. 验证环境

```powershell
python main.py
```

确认输出 `>>>>>获取预填信息成功>>>>>` 即基础链路正常。

## 抢票流程

### 抢票前 30 分钟

- 关闭 Whistle 及其他占用网络的软件（迅雷、网盘等），**关闭系统代理**
- 确保使用**有线网络**（WiFi 稳定性较差）
- 测试 `python main.py` 正常输出「获取预填信息成功」

### 抢票前 15 分钟

- 确认 `.env` 中 `SALE_START_TIME` 与实际开抢时间一致
- 建议将 `MAX_ATTEMPTS` 调至 200-300

### 抢票前 5 分钟

- 运行 `python main.py`，脚本会精确等待到开抢时间后自动循环抢票

### 抢票瞬间（关键！）

- 如果控制台卡住，**不要关闭程序**！可能是服务器高并发响应慢
- 看到 `>>>>>>抢票成功！请尽快到手机端付款！<<<<<<` 立即手机付款（10 分钟内有效）

### 备选方案

- **多设备协作**：主电脑跑脚本，备用手机同时手动抢票（不同网络，如 5G 热点）
- **代理 IP（可选）**

## 注意事项

1. **网络优先级**：企业宽带 > 家庭宽带 > 手机热点，避免使用公共 WiFi
2. **系统时间校准**（Windows）：
   ```powershell
   w32tm /resync
   ```
3. **典型失败原因**：
   - `ACCESS_TOKEN` 过期（必须抢票前 2 小时内获取）
   - 系统代理未关闭导致请求经过 Whistle 出现 SSL 证书错误
   - 电脑进入睡眠模式

## 后续规划

- **Damai 模块**（独立分支开发）：大麦网演唱会门票抢票，采用 Playwright + H5 方案，详见 `AGENTS.md`

> 成功率公式：**脚本质量(40%) + 网络延迟(30%) + 时间控制(20%) + 运气(10%)**
> 建议首次抢票用非热门场次测试，熟悉流程后再抢热门场次。
