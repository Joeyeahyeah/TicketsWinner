"""下单流程：在 H5 页面 JS 环境中调用 mtop SDK 发起下单请求。

设计要点：
- 接口: mtop.damai.buy.order.create（版本号走配置 DamaiConfig.API_VERSION，勿硬编码）
- 签名: 由页面内 JS 环境（window.mtop）自动生成 mtop x-sign，
        通过 page.evaluate 调用，不在 Python 侧逆向签名算法
- 风控: 触发滑块时截图 → Server酱推送 → 等待人工处理（不做自动化绕过）
- 参数: payload 模板化，skuId / buyerIds 优先读配置，缺省时运行时从页面获取

实现依赖真机/模拟器抓包确认（见 docs/packet_capture.md）：
- 下单接口 mtop.damai.buy.order.create 的 v 版本号与完整请求体
- 页面 mtop SDK 调用方式（window.mtop.request 签名）
- 滑块触发时的 DOM 选择器
以上字段均通过 DamaiConfig 配置化，抓包后填入 .env 即可，无需改代码。
"""
import json
import logging
import random
import time
from datetime import datetime

logger = logging.getLogger('damai.core.order')

# 成功/风控/可重试状态的判定关键字（响应字段以实际抓包为准，此处给默认值）
RETRYABLE_KEYS = ('isv.', 'system', 'busy', 'fail', 'empty', 'sold', 'stock')


def _extract_item_id(item_url: str) -> str:
    """从详情页 URL 解析 itemId（如 ?itemId=xxxx）。"""
    if not item_url:
        return ''
    for part in item_url.replace('&', '?').split('?'):
        if part.startswith('itemId='):
            return part.split('=', 1)[1]
    return ''


def _build_payload(config) -> dict:
    """构造下单请求体（模板化，版本号走配置）。

    字段以实际抓包为准，此处为参考模板，换场次/版本仅改 .env 即可。
    """
    buyer_ids = config.get_buyer_ids()
    return {
        'itemId': _extract_item_id(config.ITEM_URL),
        'skuId': config.SKU_ID,
        'quantity': config.QUANTITY,
        'buyerIds': buyer_ids,
    }


def _resolve_sku_id(page, config) -> str:
    """开抢前从详情页运行时解析 skuId（config.SKU_ID 为空时的兜底）。

    大麦页面通常把商品/票档信息挂在 window 全局或 __INITIAL_STATE__ 中，
    具体字段名以抓包为准；此处按常见结构探测，失败返回空串。
    """
    if config.SKU_ID:
        return config.SKU_ID
    try:
        sku_id = page.evaluate("""
            () => {
                const candidates = [
                    window.__INITIAL_STATE__,
                    window.__NUXT__,
                    window.g_config,
                ];
                for (const state of candidates) {
                    if (!state) continue;
                    const s = JSON.stringify(state);
                    const m = s.match(/"skuId"\\s*:\\s*"?([0-9]+)"?/);
                    if (m) return m[1];
                }
                return '';
            }
        """)
        sku_id = str(sku_id or '').strip()
    except Exception as e:  # noqa: BLE001 - 页面 JS 探测失败不应阻断流程
        logger.warning('运行时解析 skuId 失败: %s', e)
        return ''
    if sku_id:
        logger.info('运行时解析到 skuId=%s', sku_id)
    return sku_id


def _detect_slider(page) -> bool:
    """按配置化选择器检测滑块是否出现。"""
    selectors = page and getattr(page, '_slider_selectors', None)
    # 选择器由调用方通过 create_order 注入到 page 上，或从 config 读取
    if not selectors:
        return False
    try:
        for selector in selectors:
            if page.locator(selector).count() > 0:
                logger.warning('检测到滑块风控，选择器: %s', selector)
                return True
    except Exception as e:  # noqa: BLE001 - 选择器异常不影响主流程
        logger.warning('滑块检测异常: %s', e)
    return False


def _handle_slider(page, config) -> None:
    """滑块处理：截图 → Server酱推送 → 轮询等待人工完成（不自动绕过）。"""
    from . import notify

    logger.warning('触发滑块风控，进入人工辅助流程')
    try:
        config.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        screenshot_path = config.SCREENSHOT_DIR / (
            f'slider_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
        page.screenshot(path=str(screenshot_path))
        logger.info('滑块截图已保存: %s', screenshot_path)
        notify.send_screenshot(config.SERVERCHAN_SENDKEY, screenshot_path)
    except Exception as e:  # noqa: BLE001 - 截图/推送失败不阻断
        logger.warning('滑块截图或推送失败: %s', e)

    deadline = time.time() + config.SLIDER_WAIT_TIMEOUT
    while time.time() < deadline:
        if not _detect_slider(page):
            logger.info('滑块已处理，继续下单')
            return
        time.sleep(1)
    logger.warning('等待滑块处理超时（%d 秒），继续尝试下单', config.SLIDER_WAIT_TIMEOUT)


def _submit_once(page, config, payload: dict):
    """在页面 JS 环境调用 mtop SDK 发起一次下单请求，返回响应 dict 或抛异常。"""
    js = """
        (payload) => {
            return new Promise((resolve, reject) => {
                if (!window.mtop || typeof window.mtop.request !== 'function') {
                    reject(new Error('window.mtop.request 不存在，'
                        + '请确认已打开大麦 H5 页面且已登录'));
                    return;
                }
                window.mtop.request({
                    api: 'mtop.damai.buy.order.create',
                    v: %s,
                    data: payload,
                    ecode: 0,
                    timeout: %d,
                    success: (res) => resolve(res),
                    error: (err) => reject(new Error(JSON.stringify(err))),
                });
            });
        }
    """ % (json.dumps(config.API_VERSION), int(config.REQUEST_TIMEOUT * 1000))

    return page.evaluate(js, payload)


def create_order(page, config):
    """下单主流程。

    :param page: 已加载登录态、已打开演出详情页的 Playwright Page
    :param config: DamaiConfig
    :return: 下单成功返回订单信息 dict，失败返回 None
    """
    from . import notify

    # 将滑块选择器挂到 page 上，供 _detect_slider 使用
    page._slider_selectors = config.SLIDER_SELECTORS

    payload = _build_payload(config)
    if not payload.get('skuId'):
        resolved = _resolve_sku_id(page, config)
        if resolved:
            payload['skuId'] = resolved
    logger.info('下单参数: api=mtop.damai.buy.order.create v=%s itemId=%s skuId=%s',
                config.API_VERSION, payload.get('itemId'), payload.get('skuId'))

    for attempt in range(1, config.MAX_ATTEMPTS + 1):
        # 每次重试前检测滑块（人工处理过程中可能触发）
        if _detect_slider(page):
            _handle_slider(page, config)

        try:
            start = time.monotonic()
            response = _submit_once(page, config, payload)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info('下单请求%d 耗时 %.0fms 响应: %s',
                        attempt, elapsed_ms, json.dumps(response, ensure_ascii=False)[:200])
        except Exception as e:  # noqa: BLE001 - 页面 JS/网络异常均需重试
            logger.warning('下单请求%d 出错: %s', attempt, e)
            time.sleep(random.uniform(config.RETRY_INTERVAL_MIN, config.RETRY_INTERVAL_MAX))
            continue

        # 响应状态机（字段以实际抓包为准，此处给通用判定）
        ret = _parse_response(response)
        if ret == 'success':
            logger.info('>>>>>> 下单成功！请尽快到手机端付款！<<<<<<')
            return response
        if ret == 'slider':
            _handle_slider(page, config)
            continue
        # 缺货/失败：随机间隔后重试
        logger.info('下单请求%d 未成功，随机间隔后重试', attempt)
        time.sleep(random.uniform(config.RETRY_INTERVAL_MIN, config.RETRY_INTERVAL_MAX))

    logger.warning('超过最大下单次数(%d)，下单流程结束', config.MAX_ATTEMPTS)
    return None


def _parse_response(response: dict) -> str:
    """解析下单响应，返回 'success' / 'slider' / 'retry'。

    大麦 mtop 响应常见结构: {ret: [...], data: {...}}，ret[0] 形如
    'SUCCESS::调用成功' 或 'FAIL_SYS_USER_VALIDATE::xxx'（滑块）。
    具体以实际抓包为准，此处做宽松匹配。
    """
    if not isinstance(response, dict):
        return 'retry'

    raw = json.dumps(response, ensure_ascii=False)
    # 成功：含 "SUCCESS" 且不带 fail/error
    if 'SUCCESS' in raw.upper() and 'fail' not in raw.lower():
        return 'success'

    # 滑块：含典型验证关键字
    slider_markers = ('punish', 'ncaptcha', 'captcha', 'slide', 'verify',
                      'VALIDATE', 'CHECK')
    if any(m in raw for m in slider_markers):
        return 'slider'

    return 'retry'
