# 大麦下单接口抓包指引

> 本指引用于真机/模拟器抓取大麦下单链路的真实请求，为 `damai/core/order.py` 下单实现提供数据依据。
> 仅限**本人账号、本人自用**，抓包数据仅用于技术研究，切勿用于任何商用或非法用途。

## 〇、参数分类与抓包时机（先读这个）

抓包参数按"持久度"分两类，决定何时抓、何时重抓：

### A 类：持久参数（换场次才需重抓）

抓一次写入 `damai/.env` 即可，多次抢票复用：

| 参数 | 来源 | 用途 |
|---|---|---|
| `DAMAI_ITEM_URL` | 详情页地址栏 | 打开演出页（换场次变） |
| `BUYER_IDS` | 大麦「常用观演人」或确认订单页接口 | 下单时选观演人 |
| `RESERVE_SUBMIT_SELECTOR` | 详情页 F12 检查「预约抢票」按钮 | 预约入口选择器 |
| `BUY_NOW_SELECTOR` | 详情页 F12 检查「立即抢票」按钮 | 开抢入口选择器（通常与上同） |
| `RESERVE_SKU_SELECTOR` | 详情页 F12 检查票档元素 | 预约时选票档 |
| `RESERVE_QTY_SELECTOR` | 详情页 F12 检查数量输入框 | 预约时设数量 |
| `RESERVE_BUYER_SELECTOR` | 确认订单页 F12 检查观演人选择 | 预约时选观演人（可留空） |
| `SLIDER_SELECTORS` | 触发滑块后 F12 检查 captcha 元素 | 滑块检测（可先用默认值，触发后补） |
| `SLIDER_WAIT_TIMEOUT` | 无需抓包，按需设 | 滑块人工处理超时（默认 120 秒） |

### B 类：易变参数（抢票前一天/2 小时内重抓）

每次抢票前必须重新确认：

| 参数 | 来源 | 为何易变 |
|---|---|---|
| `SALE_START_TIME` | 详情页显示 | 换场次变 |
| `DAMAI_API_VERSION` | 下单接口 `v` 参数 | 大麦版本更新会变 |
| `SKU_ID` | 选票档时 mtop 响应 | **换场次必变**；但 `order.py` 会运行时兜底探测，可留空 |
| `QUANTITY` | 用户自定 | 按需 |
| `SERVERCHAN_SENDKEY` | Server酱官网 | 长期有效但建议定期确认 |
| `storage_state.json` | `python -m damai.main login` 扫码 | cookie 过期需重登（建议抢票前一天扫） |

### 抓包节奏建议

1. **现在抓 A 类**：打开详情页 F12 抓选择器与观演人 ID，写入 `damai/.env`
2. **抢票前一天**：`python -m damai.main login` 扫码保存登录态；确认 `SALE_START_TIME`
3. **抢票前 2 小时**：抓 `DAMAI_API_VERSION` 与下单请求体（见第五节）；跑 `python -m damai.main reserve` 预约
4. **抢票当天**：`python -m damai.main grab` 预取 + 下单

---

## 一、目标与产出

抓包完成后，你需要得到并回填下方「抓包结果记录模板」，实现阶段将直接读取这些数据：

1. **下单接口** `mtop.damai.buy.order.create` 的 **`v` 版本号** 与 **完整请求体**
2. 详情页/确认订单页中**返回 `skuId` 列表的前置接口**（用于开抢前预取 skuId）
3. 页面内 **mtop SDK 调用方式**（`window.mtop` 是否存在、页面自有封装）
4. 滑块风控触发时的 **URL 特征** 与 **DOM 选择器**

## 二、抓包工具：Whistle（首选）

项目已在 WeixinMiniApp 模块使用过 Whistle，此处复用同一工具。

### 2.1 安装与启动

```powershell
npm install -g whistle
w2 start
```

控制台地址 `http://127.0.0.1:8899`，代理端口默认 `8899`。

### 2.2 配置 HTTPS 抓包

1. 浏览器打开 `http://127.0.0.1:8899`
2. 右上角 **HTTPS** → **Download RootCA**，下载根证书
3. 安装根证书（见下方「证书安装」小节）
4. 在 **HTTPS** 面板中勾选 **Capture TUNNEL CONNECTs**（抓取 CONNECT 之前的域名，便于定位 mtop 接口）

## 三、抓包环境

大麦下单为 **H5 页面 + mtop 接口**，有两条抓包路径，**建议优先走 PC 浏览器**（无需真机证书，最省事）：

### 3.1 方案 A：PC 浏览器直接抓 H5（推荐，先做这个）

大麦 H5 页面本身可在 PC 浏览器打开，mtop 请求由页面 JS 发出，直接配合 Whistle 代理即可抓到，无需真机。

1. 启动 Whistle，将 **Windows 系统代理**设为 `127.0.0.1:8899`
2. 安装 Whistle 根证书到「本地计算机 → 受信任的根证书颁发机构」（README 已记录该步骤）
3. 浏览器（建议 Chrome 无痕窗口）打开大麦 H5 演出详情页（`https://m.damai.cn/...`）
4. 走完整操作路径（见第四节），在 Whistle 控制台 Network 中筛选 `mtop` 请求

> 注意：H5 上的「立即购买」可能跳转 App 或提示在 App 内操作，若 H5 无法完成下单，改用方案 B。

### 3.2 方案 B：安卓模拟器 / 真机（H5 无法下单时的兜底）

**模拟器**（MuMu / 雷电，大屏易操作，推荐）或**真机**（同 WiFi）：

1. 模拟器/手机网络设置 → 手动代理，地址填**电脑局域网 IP**（`ipconfig` 查 IPv4），端口 `8899`
2. 安装 Whistle 根证书：
   - **Android 7+**：用户证书默认不被 App 信任，需将证书安装到**系统证书区**（模拟器可开启 root 后把证书文件放入 `/system/etc/security/cacerts/`；真机需 root 或用 Magisk 模块）
   - **Android 6 及以下**：直接安装用户证书即可被 App 信任
3. 登录大麦 App/H5，走完整操作路径抓包

> 若无法安装系统证书、抓不到 mtop 明文，优先回到方案 A。

## 四、目标操作路径

无论走哪条路径，都按以下顺序操作，**到支付页前停止，不实际付款**：

1. **登录**大麦账号
2. 打开**目标演出详情页**（对应 `.env` 中 `DAMAI_ITEM_URL`）
3. 选择**票价 / 票档**（这一步会触发获取 `skuId` 列表的接口）
4. 点**「立即购买」** → 进入**确认订单页**（选观演人、数量）
5. 点**「提交订单」** → 停在**支付页前**（此时 `mtop.damai.buy.order.create` 已发出）

每一步都在 Whistle 里留意新出现的 `mtop` 请求。

### 4.5 开抢前的预约操作（大麦预约抢票机制）

大麦开抢前的真实机制：开抢前详情页主按钮文案为「**预约抢票**」而非「立即购买」。
抢票前一天/几小时需提前预约，倒计时归零后按钮变为「立即抢票」，点击后自动勾选
已预约的票档/数量直跳确认订单页（跳过逐项选择）。

抓包时按以下顺序操作，记录对应选择器与接口：

1. 打开**目标演出详情页**（开抢前状态，按钮应为「预约抢票」）
2. 选择**票价 / 票档**（与 5.2 节获取 skuId 的前置接口一致）
3. 设置**数量**
4. （可选）选择**观演人**（预约阶段通常不选，确认订单页才选）
5. 点**「预约抢票」**主按钮 → 若弹出二次确认，点**「提交抢票预约」**
6. 倒计时归零后，按钮变为**「立即抢票」** → 点击 → 自动勾选已预约内容直跳确认订单页

记录要点：
- 「预约抢票」「提交抢票预约」「立即抢票」三个按钮的 **DOM 选择器**（右键「检查」复制）
- 预约提交时触发的 mtop 接口名（如 `mtop.damai.*.reserve*`，以实际抓到为准）与版本号、请求体
- 确认订单页的 **URL 模式**（如 `buy.damai.cn/order/confirm?...`），用于 grab 流程判断是否已进入确认页

## 五、需要记录的目标字段清单

### 5.1 下单接口 `mtop.damai.buy.order.create`

在 Whistle 中点击该请求，记录：

| 项目 | 位置 | 说明 |
|---|---|---|
| `v` 版本号 | URL query 或请求体 | 如 `?v=1.0`，**务必记录实际值**，填入 `DAMAI_API_VERSION` |
| `itemId` | 请求体 | 演出 ID，通常可从详情页 URL 解析 |
| `skuId` | 请求体 | 票档 ID，下单关键字段 |
| `quantity` | 请求体 | 购票数量 |
| `buyerIds` / 观演人结构 | 请求体 | 观演人 ID 数组或对象结构，**完整记录嵌套结构** |
| `dmChannel` 等其他字段 | 请求体 | 一并记录完整请求体 JSON |

**重点**：把该请求的**完整请求体 JSON**原样复制到记录模板（见第六节），不要只记字段名。

### 5.2 获取 `skuId` 的前置接口

在「选票档」这一步，找到返回 `skuId` 列表的 mtop 接口（常见命名如 `mtop.damai.item.detail.getitem` 或类似，**以实际抓到为准**），记录：

- 接口名与 `v` 版本号
- 请求参数（输入什么 → 输出 skuId 列表）
- 响应中 skuId 与票价/票档名称的对应关系（用于配置正确的票档）

### 5.3 页面 mtop SDK 调用方式

在确认订单页，用浏览器开发者工具 Console 验证（**用于确定 order.py 如何发起请求**）：

```js
// 查看是否存在 window.mtop
console.log(typeof window.mtop);
// 若存在，查看其方法
console.log(Object.keys(window.mtop || {}));
```

记录结论：

- `window.mtop` 是否存在？其 `request` 方法签名（参数结构）是什么？
- 或页面是否有自有请求封装（如全局 `window.__damaiApi` 之类）？

> 这将决定 `order.py` 里 `page.evaluate` 具体调用哪个对象、传什么参数。

### 5.4 滑块风控 DOM 特征

提交订单若触发滑块，记录：

- 触发后的 **URL 特征**（如包含 `_____tmd_____/punish`、`ncaptcha`、`verify` 等）
- 滑块 **iframe / 元素的 DOM 选择器**（右键「检查」复制 selector）
- 滑块元素出现的大致时机与是否遮挡提交按钮

> 这些选择器将填入 `order.py` 的滑块检测配置。

### 5.5 预约抢票相关字段（开抢前预取与预约入口）

大麦预约抢票机制相关字段，供 `reserve` 子命令与 `grab` 流程预取阶段使用：

| 项目 | 用途 | 说明 |
|---|---|---|
| `RESERVE_SUBMIT_SELECTOR` | 预约主按钮选择器 | 开抢前详情页「预约抢票」/「提交抢票预约」按钮，填入 `.env` |
| `BUY_NOW_SELECTOR` | 立即抢票入口选择器 | 开抢后详情页「立即抢票」按钮，grab 预取阶段点击它直跳确认订单页 |
| `RESERVE_SKU_SELECTOR` | 预约时票档选择器 | 选票档的 DOM 选择器，抓包后填入 |
| `RESERVE_QTY_SELECTOR` | 预约时数量输入框选择器 | 设数量的 DOM 选择器，留空则不自动设置 |
| `RESERVE_BUYER_SELECTOR` | 预约时观演人选择器 | 预约阶段通常不选观演人，确认订单页才选 |

#### 5.5.1 预约接口（若存在）

预约提交时触发的 mtop 接口（接口名以实际抓到为准，可能为 `mtop.damai.*.reserve*`）：

- 接口名与 `v` 版本号
- 完整请求体 JSON
- 响应中预约成功的判定字段（如 `ret[0]` 含 `SUCCESS`）

> 当前 `reserve.py` 仅做页面级点击交互，未直接调用预约接口；若后续发现预约必须走
> 接口而非页面点击，再补充接口级实现。

#### 5.5.2 确认订单页 mtop 验证

`window.mtop` SDK 仅存在于「确认订单页」而非详情页。在确认订单页用 Console 验证：

```js
// 必须在确认订单页执行，详情页通常返回 undefined
console.log(typeof window.mtop);          // 期望: "object"
console.log(typeof window.mtop.request);  // 期望: "function"
```

若确认订单页也无 `window.mtop`，需抓包确认页面自有请求封装（如 `window.__damaiApi`），
并调整 `order.py` 的 `_submit_once` 调用方式。

#### 5.5.3 确认订单页 URL 模式

记录确认订单页的 URL 模式（如 `https://buy.damai.cn/order/confirm?...`），
用于 `grab` 流程判断预取阶段是否已成功进入确认订单页。

## 六、抓包结果记录模板

将下方模板复制到新文件（如 `damai/docs/packet_capture_result.md`）填写，完成后交给实现阶段：

```markdown
# 抓包结果记录

> 抓包日期：____　环境：□ PC浏览器H5　□ 模拟器　□ 真机

## 1. 下单接口 mtop.damai.buy.order.create

### 版本号 v
`DAMAI_API_VERSION = ______`

### 完整请求体（原样复制 JSON）
```json
{
  "itemId": "",
  "skuId": "",
  "quantity": 1,
  "buyerIds": [],
  "...": "..."
}
```

## 2. 获取 skuId 的前置接口

- 接口名 / v：`______`
- 请求参数：
- skuId 与票档对应关系：
  | 票档名称 | 票价 | skuId |
  |---|---|---|
  | | | |

## 3. 页面 mtop SDK 调用方式

- window.mtop 是否存在：____
- 调用方式（示例代码）：

## 4. 滑块风控 DOM 特征

- 触发 URL 特征：`______`
- 滑块 iframe/元素选择器：`______`
- 补充说明：

## 5. 预约抢票相关字段（见 5.5 节）

### 预约/立即抢票按钮选择器

| 选择器 | 值 |
|---|---|
| `RESERVE_SUBMIT_SELECTOR` | ______ |
| `BUY_NOW_SELECTOR` | ______ |
| `RESERVE_SKU_SELECTOR` | ______ |
| `RESERVE_QTY_SELECTOR` | ______ |
| `RESERVE_BUYER_SELECTOR` | ______ |

### 预约接口（若存在）

- 接口名 / v：`______`
- 完整请求体 JSON：

### 确认订单页

- URL 模式：`______`
- `window.mtop` 是否存在：______
- `window.mtop.request` 是否为 function：______
```

## 七、抓包注意事项

- 抓包结束后**务必关闭系统代理 / 模拟器代理**，否则影响正常上网
- 下单请求涉及个人账号信息，抓包结果文件**不要提交到仓库**（建议加入 `.gitignore`）
- `v` 版本号与请求体会随大麦版本更新变化，**换场次/升级后需重新抓包确认**
