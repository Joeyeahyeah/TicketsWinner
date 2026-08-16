"""预约抢票流程：开抢前预选票档/数量/观演人并提交抢票预约。

大麦网开抢前的真实机制（2024-2025 实测有效）：
- 开抢前详情页主按钮文案为「预约抢票」而非「立即购买」
- 用户可提前预约：选想看的场次/票档/数量 → 点「提交抢票预约」
- 倒计时归零时，「预约抢票」按钮自动变为「立即抢票」
- 点击「立即抢票」后自动勾选已预约的票档/数量，跳过逐项选择直跳确认订单页

本模块负责「开抢前的预约」这一步，grab 流程会在开抢前 N 秒通过预约入口
进入确认订单页预取真实 skuId/buyerIds，开抢瞬间直接发起 mtop 下单。

设计要点：
- 所有真机相关选择器（票档/数量/观演人/预约入口）走 DamaiConfig 配置化
- 选择器缺省时降级为「提示用户手动点击」而非硬失败，避免阻塞
- 预约成功后把 skuId/buyerIds/itemId/数量写入 RESERVE_STATE_PATH，
  供 grab 预取阶段优先读本地缓存
- 不自动绕过任何风控；触发滑块由调用方处理
"""
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger('damai.core.reserve')

# 等待元素出现的默认超时（秒），抓包后可按页面响应调整
_WAIT_TIMEOUT = 10


def _try_click(page, selector: str, label: str, timeout: int = _WAIT_TIMEOUT) -> bool:
    """按选择器点击元素，元素不存在或不可点时降级为提示。

    :return: 成功点击返回 True，降级/失败返回 False
    """
    if not selector:
        logger.warning('%s 选择器未配置，请手动点击完成该步骤', label)
        return False
    try:
        locator = page.locator(selector).first
        locator.wait_for(state='visible', timeout=timeout * 1000)
        locator.click()
        logger.info('已点击 %s (%s)', label, selector)
        return True
    except Exception as e:  # noqa: BLE001 - 选择器交互失败应降级而非阻断
        logger.warning('点击 %s 失败 (%s): %s，请手动完成', label, selector, e)
        return False


def _resolve_sku_id_from_page(page) -> str:
    """从详情页运行时探测 skuId（与 order._resolve_sku_id 同源逻辑）。

    预约阶段用于把探测到的 skuId 一并写入 reserve_state，供 grab 复用。
    """
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
        return str(sku_id or '').strip()
    except Exception as e:  # noqa: BLE001
        logger.warning('预约阶段探测 skuId 失败: %s', e)
        return ''


def save_reserve_state(config, state: dict) -> None:
    """持久化预约状态到 RESERVE_STATE_PATH（grab 预取阶段会读取）。"""
    path = Path(config.RESERVE_STATE_PATH)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                        encoding='utf-8')
        logger.info('预约状态已保存: %s', path)
    except OSError as e:
        logger.warning('保存预约状态失败: %s', e)


def load_reserve_state(config) -> dict:
    """读取本地预约状态缓存（grab 预取阶段优先读，页面预取作为验证/兜底）。"""
    path = Path(config.RESERVE_STATE_PATH)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        logger.warning('读取预约状态失败: %s', e)
        return {}


def submit_reserve(page, config) -> bool:
    """在详情页执行预约抢票流程。

    流程：选票档 → 设数量 → 选观演人 → 点「预约抢票」→ 点「提交抢票预约」
    → 探测 skuId 写入本地缓存。

    :param page: 已加载登录态、已打开演出详情页的 Playwright Page
    :param config: DamaiConfig
    :return: 预约提交成功返回 True（按页面跳转/按钮文案变化判定）
    """
    from . import notify

    logger.info('开始预约抢票流程')

    # 1. 选票档（可选，选择器留空时提示用户手动选）
    if config.RESERVE_SKU_SELECTOR:
        _try_click(page, config.RESERVE_SKU_SELECTOR, '票档')
        time.sleep(0.3)

    # 2. 设数量（可选）
    if config.RESERVE_QTY_SELECTOR and config.QUANTITY > 1:
        try:
            page.locator(config.RESERVE_QTY_SELECTOR).first.fill(
                str(config.QUANTITY))
            logger.info('已设置数量: %d', config.QUANTITY)
        except Exception as e:  # noqa: BLE001
            logger.warning('设置数量失败 (%s): %s，请手动调整',
                           config.RESERVE_QTY_SELECTOR, e)
        time.sleep(0.2)

    # 3. 选观演人（可选；预约阶段通常不选观演人，确认订单页才选）
    if config.RESERVE_BUYER_SELECTOR:
        for buyer_id in config.get_buyer_ids():
            # 观演人选择器可能需要按 id 定位，此处按通用点击处理
            _try_click(page, config.RESERVE_BUYER_SELECTOR, f'观演人 {buyer_id}')

    # 4. 点「预约抢票」主按钮
    clicked = _try_click(page, config.RESERVE_SUBMIT_SELECTOR, '预约抢票按钮')
    if not clicked:
        logger.warning('预约主按钮未自动点击，请在浏览器手动点击「预约抢票」')

    # 5. 若弹出「提交抢票预约」二次确认，尝试点击（选择器与主按钮相同时会自然跳过）
    time.sleep(0.5)
    _try_click(page, config.RESERVE_SUBMIT_SELECTOR, '提交抢票预约',
               timeout=3)

    # 6. 探测 skuId 并保存预约状态（grab 预取阶段会优先读本地缓存）
    sku_id = config.SKU_ID or _resolve_sku_id_from_page(page)
    state = {
        'itemId': _extract_item_id(config.ITEM_URL),
        'skuId': sku_id,
        'buyerIds': config.get_buyer_ids(),
        'quantity': config.QUANTITY,
        'reservedAt': int(time.time()),
    }
    save_reserve_state(config, state)

    logger.info('预约流程已完成，skuId=%s，请核对浏览器页面是否已进入预约状态',
                sku_id or '(未探测到，需抓包填 SKU_ID)')
    notify.send_text(
        config.SERVERCHAN_SENDKEY, '大麦预约完成',
        f'skuId={sku_id or "未探测到"}\n请到大麦首页「我的预约」核对')
    return True


def _extract_item_id(item_url: str) -> str:
    """从详情页 URL 解析 itemId（与 order._extract_item_id 同源逻辑）。"""
    if not item_url:
        return ''
    for part in item_url.replace('&', '?').split('?'):
        if part.startswith('itemId='):
            return part.split('=', 1)[1]
    return ''
