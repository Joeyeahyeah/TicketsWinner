"""下单流程：拦截页面真实 mtop 请求实现下单。

设计要点（抓包确认后的真实方案）：
- 接口: mtop.damai.trade.order.create.h5（走配置 DamaiConfig.ORDER_API）
- 请求体: 大麦 H5 确认订单页的组件状态树（含 signKey/submitref 等动态字段），
          无法在 Python 侧构造，必须由页面自己生成
- 下单方式: 用 page.route 拦截 mtop 请求，点击页面「提交订单」按钮触发，
            拦截器捕获响应判断成功/失败
- 风控: 触发滑块时截图 → Server酱推送 → 等待人工处理（不做自动化绕过）

实现依赖真机/模拟器抓包确认（见 docs/packet_capture.md）：
- 提交订单按钮选择器 SUBMIT_ORDER_SELECTOR（抓包后填入 .env）
- 滑块触发时的 DOM 选择器
"""
import json
import logging
import random
import time
from datetime import datetime

logger = logging.getLogger('damai.core.order')


def _detect_slider(page) -> bool:
    """按配置化选择器检测滑块是否出现。"""
    if not page or page.is_closed():
        return False
    selectors = getattr(page, '_slider_selectors', None)
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


def _click_submit(page, config) -> dict | None:
    """点击提交订单按钮，拦截 mtop 下单响应。

    大麦 H5 下单请求体是整个页面组件树（含 signKey/submitref 动态字段），
    Python 侧无法构造，必须点击页面「提交订单」按钮让页面自己生成请求。
    用 page.route 拦截 mtop 响应，返回给 Python 判断。
    """
    captured = {'response': None}

    def handle_route(route):
        request = route.request
        if config.ORDER_API in request.url:
            try:
                # 继续请求，捕获响应
                response = route.fetch()
                try:
                    body = response.json()
                except Exception:
                    body = {'raw': response.text()[:500]}
                captured['response'] = body
                logger.info('拦截到下单响应: %s',
                            json.dumps(body, ensure_ascii=False)[:200])
                route.fulfill(response=response)
            except Exception as e:  # noqa: BLE001
                logger.warning('拦截下单响应失败: %s', e)
                route.continue_()
        else:
            route.continue_()

    # 注册拦截器，匹配 mtop 下单接口
    page.route('**/mtop.damai.trade.order.create*', handle_route)

    try:
        # 点击提交订单按钮
        selector = config.SUBMIT_ORDER_SELECTOR
        if not selector:
            logger.error('SUBMIT_ORDER_SELECTOR 未配置，无法点击提交按钮')
            return None
        locator = page.locator(selector).first
        locator.wait_for(state='visible', timeout=config.PAGE_LOAD_TIMEOUT * 1000)
        start = time.monotonic()
        locator.click()
        logger.info('已点击提交订单按钮，等待响应')

        # 等待拦截到响应（最多等 REQUEST_TIMEOUT + 缓冲）
        deadline = time.monotonic() + config.REQUEST_TIMEOUT + 5
        while time.monotonic() < deadline:
            if captured['response'] is not None:
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.info('下单响应耗时 %.0fms', elapsed_ms)
                return captured['response']
            time.sleep(0.05)
        logger.warning('点击提交后 %d 秒未拦截到下单响应',
                       int(config.REQUEST_TIMEOUT + 5))
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning('点击提交订单失败: %s', e)
        return None
    finally:
        try:
            page.unroute('**/mtop.damai.trade.order.create*', handle_route)
        except Exception:  # noqa: BLE001
            pass


def create_order(page, config):
    """下单主流程。

    :param page: 已加载登录态的 Playwright Page。**必须已处于「确认订单页」**
        （选好票档/数量/观演人后的确认订单页）。grab 流程通过预约入口进入
        确认订单页后再调用本函数（见 main._prefetch_sku_before_start）。
    :param config: DamaiConfig
    :return: 下单成功返回订单信息 dict，失败返回 None
    """
    from . import notify

    # 将滑块选择器挂到 page 上，供 _detect_slider 使用
    page._slider_selectors = config.SLIDER_SELECTORS

    logger.info('开始下单流程: 点击提交订单按钮 → 拦截 mtop 响应')

    for attempt in range(1, config.MAX_ATTEMPTS + 1):
        # 页面/浏览器被关闭（如手动关闭）时立即退出，避免刷垃圾重试日志
        if page.is_closed():
            logger.warning('页面已关闭，终止下单流程')
            return None

        # 每次重试前检测滑块（人工处理过程中可能触发）
        if _detect_slider(page):
            _handle_slider(page, config)

        response = _click_submit(page, config)
        if response is None:
            logger.warning('下单请求%d 未捕获到响应', attempt)
            time.sleep(random.uniform(config.RETRY_INTERVAL_MIN,
                                      config.RETRY_INTERVAL_MAX))
            continue

        logger.info('下单请求%d 响应: %s', attempt,
                    json.dumps(response, ensure_ascii=False)[:200])

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
        time.sleep(random.uniform(config.RETRY_INTERVAL_MIN,
                                  config.RETRY_INTERVAL_MAX))

    logger.warning('超过最大下单次数(%d)，下单流程结束', config.MAX_ATTEMPTS)
    return None
