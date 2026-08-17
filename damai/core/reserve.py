"""预约抢票流程：开抢前预选票档并提交抢票预约。

大麦 H5 真实交互顺序（抓包验证）：
1. 详情页底部主按钮文案「预约抢票」/「立即购买」
2. 点主按钮 → 弹出选票弹窗（body > div.bui-modal > div.sku-pop-wrapper）
3. 在弹窗里选票价 → 点弹窗「确认」→ 进入确认订单页
4. 确认订单页选观演人、数量 → 点「提交订单」触发 mtop 下单

本模块负责「开抢前的预约」这一步（步骤 1-3），grab 流程会在开抢前 N 秒
重复步骤 1-3 进入确认订单页，开抢瞬间直接点「提交订单」下单。

设计要点：
- 所有真机相关选择器走 DamaiConfig 配置化
- 选择器缺省时降级为「提示用户手动点击」而非硬失败，避免阻塞
- 预约成功后把 itemId/buyerIds/数量写入 RESERVE_STATE_PATH 供 grab 复用
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

    大麦 H5 真实交互顺序（抓包验证）：
    1. 详情页底部主按钮文案「预约抢票」/「立即购买」
    2. 点主按钮 → 弹出选票弹窗（body > div.bui-modal > div.sku-pop-wrapper）
    3. 在弹窗里选票价
    4. 点弹窗「确认」按钮 → 进入确认订单页（或预约成功页）
    5. 若有「提交抢票预约」二次确认则点击

    :param page: 已加载登录态、已打开演出详情页的 Playwright Page
    :param config: DamaiConfig
    :return: 预约提交成功返回 True（按页面跳转/按钮文案变化判定）
    """
    from . import notify

    logger.info('开始预约抢票流程')

    # 1. 点「预约抢票」/「立即购买」主按钮 → 弹出选票弹窗
    clicked = _try_click(page, config.RESERVE_SUBMIT_SELECTOR, '预约抢票/立即购买主按钮')
    if not clicked:
        logger.warning('主按钮未自动点击，请在浏览器手动点击')
        return False

    # 2. 等选票弹窗弹出，在弹窗里选票价
    if config.RESERVE_SKU_SELECTOR:
        time.sleep(0.5)  # 等弹窗动画完成
        _try_click(page, config.RESERVE_SKU_SELECTOR, '票档（弹窗内）')
        time.sleep(0.3)

    # 3. 设数量（可选，弹窗内可能有数量选择）
    if config.RESERVE_QTY_SELECTOR and config.QUANTITY > 1:
        try:
            page.locator(config.RESERVE_QTY_SELECTOR).first.fill(
                str(config.QUANTITY))
            logger.info('已设置数量: %d', config.QUANTITY)
        except Exception as e:  # noqa: BLE001
            logger.warning('设置数量失败 (%s): %s，请手动调整',
                           config.RESERVE_QTY_SELECTOR, e)
        time.sleep(0.2)

    # 4. 点弹窗「确认」按钮 → 进入确认订单页/预约成功页
    if config.SKU_CONFIRM_SELECTOR:
        time.sleep(0.3)
        _try_click(page, config.SKU_CONFIRM_SELECTOR, '选票弹窗确认按钮')

    # 5. 若弹出「提交抢票预约」二次确认，尝试点击（与主按钮选择器相同时自然跳过）
    time.sleep(0.5)
    _try_click(page, config.RESERVE_SUBMIT_SELECTOR, '提交抢票预约（二次确认）',
               timeout=3)

    # 6. 保存预约状态（供 grab 预取阶段读本地缓存，order.py 改为拦截真实请求后 skuId 非必需）
    state = {
        'itemId': _extract_item_id(config.ITEM_URL),
        'skuId': config.SKU_ID,
        'buyerIds': config.get_buyer_ids(),
        'quantity': config.QUANTITY,
        'reservedAt': int(time.time()),
    }
    save_reserve_state(config, state)

    logger.info('预约流程已完成，请核对浏览器页面是否已进入预约状态')
    notify.send_text(
        config.SERVERCHAN_SENDKEY, '大麦预约完成',
        f'请到大麦首页「我的预约」核对')
    return True


def _extract_item_id(item_url: str) -> str:
    """从详情页 URL 解析 itemId（与 order._extract_item_id 同源逻辑）。"""
    if not item_url:
        return ''
    for part in item_url.replace('&', '?').split('?'):
        if part.startswith('itemId='):
            return part.split('=', 1)[1]
    return ''
