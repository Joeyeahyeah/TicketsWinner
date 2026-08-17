"""大麦抢票模块入口

用法:
    python -m damai.main login     # 扫码登录，保存 storage_state（抢票前一天执行）
    python -m damai.main reserve   # 开抢前预约抢票：点主按钮弹弹窗→选票档→确认
    python -m damai.main grab      # 加载登录态，开抢前进入确认订单页，到达开抢时间后下单

大麦 H5 真实交互顺序（抓包验证）：
1. 详情页底部主按钮（「预约抢票」/「立即购买」/「立即抢票」文案随开抢状态变）
2. 点主按钮 → 弹出选票弹窗（body > div.bui-modal > div.sku-pop-wrapper）
3. 在弹窗里选票价 → 点弹窗「确认」→ 进入确认订单页
4. 确认订单页选观演人、数量 → 点「提交订单」触发 mtop.damai.trade.order.create.h5

grab 流程在开抢前 N 秒重复步骤 1-3 进入确认订单页，开抢瞬间直接点「提交订单」下单。
order.py 用 page.route 拦截 mtop 响应判断成功/失败（请求体由页面生成，Python 不构造）。
"""
import argparse
import logging
import sys
import time

from .config import DamaiConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('damai')


def cmd_login() -> int:
    from .browser.login import login
    return 0 if login(DamaiConfig) else 1


def cmd_reserve() -> int:
    """开抢前预约抢票：选票档/数量/观演人并提交抢票预约，保存预约状态。"""
    DamaiConfig.validate_reserve()
    item_url = DamaiConfig.ITEM_URL
    assert item_url, 'validate_reserve 已校验 ITEM_URL 非空'

    from .browser.browser_manager import browser_session
    from .core import reserve

    # 预约需用户在场观察页面交互，强制有头
    with browser_session(DamaiConfig, headless=False) as context:
        page = context.new_page()
        logger.info('打开演出详情页: %s', item_url)
        page.goto(item_url, timeout=DamaiConfig.PAGE_LOAD_TIMEOUT * 1000)

        ok = reserve.submit_reserve(page, DamaiConfig)
        if ok:
            logger.info('>>>>>> 预约完成，请到大麦首页「我的预约」核对 <<<<<<')
            logger.info('抢票前请运行: python -m damai.main grab')
        else:
            logger.warning('预约流程未完成，请检查浏览器页面或抓包补充选择器')
    return 0 if ok else 1


def _enter_confirm_page(page, config) -> None:
    """开抢前预取阶段：走详情页交互进入确认订单页。

    大麦 H5 真实交互顺序（抓包验证）：
    1. 点详情页主按钮 → 弹出选票弹窗
    2. 在弹窗里选票价
    3. 点弹窗「确认」→ 进入确认订单页（「提交订单」按钮所在页面）

    本函数重复这一流程，让 page 到达确认订单页，
    order.create_order 即可点击「提交订单」触发 mtop 下单。
    失败时降级（page 留在详情页），order.create_order 会因找不到提交按钮而报错。
    """
    from .core.reserve import _try_click

    # 1. 点主按钮弹弹窗
    _try_click(page, config.BUY_NOW_SELECTOR, '立即抢票/立即购买主按钮')

    # 2. 在弹窗里选票价
    if config.RESERVE_SKU_SELECTOR:
        time.sleep(0.5)  # 等弹窗动画
        _try_click(page, config.RESERVE_SKU_SELECTOR, '票档（弹窗内）')
        time.sleep(0.3)

    # 3. 点弹窗「确认」→ 进入确认订单页
    if config.SKU_CONFIRM_SELECTOR:
        time.sleep(0.3)
        _try_click(page, config.SKU_CONFIRM_SELECTOR, '选票弹窗确认按钮')

    logger.info('预取阶段完成，page 应已进入确认订单页')


def cmd_grab() -> int:
    DamaiConfig.validate()
    item_url = DamaiConfig.ITEM_URL
    assert item_url, 'validate 已校验 ITEM_URL 非空'

    from .browser.browser_manager import browser_session
    from .core import notify, order, scheduler

    offset = scheduler.calibrate_clock(timeout=DamaiConfig.REQUEST_TIMEOUT)
    target_ts = scheduler.target_timestamp(DamaiConfig.SALE_START_TIME)

    with browser_session(DamaiConfig) as context:
        page = context.new_page()
        logger.info('打开演出详情页: %s', item_url)
        page.goto(item_url, timeout=DamaiConfig.PAGE_LOAD_TIMEOUT * 1000)

        # 开抢前 N 秒进入预取阶段：走预约入口预取真实 skuId/buyerIds
        prefetch_at = target_ts - DamaiConfig.GET_SKU_BEFORE_START
        logger.info('预取阶段将在 %s 开始（开抢前 %d 秒）',
                    _fmt_local(prefetch_at, offset),
                    DamaiConfig.GET_SKU_BEFORE_START)
        scheduler.wait_until_start_time(prefetch_at, offset)
        logger.info('进入预取阶段：走详情页交互进入确认订单页')
        try:
            _enter_confirm_page(page, DamaiConfig)
        except Exception as e:  # noqa: BLE001 - 预取失败不阻断，order 兜底
            logger.warning('预取阶段失败，降级为开抢后由 order 兜底: %s', e)

        logger.info('等待开抢时间: %s', DamaiConfig.SALE_START_TIME)
        scheduler.wait_until_start_time(target_ts, offset)
        logger.info('到达开抢时间，开始下单流程')

        result = order.create_order(page, DamaiConfig)
        if result:
            logger.info('>>>>>> 抢票成功！请尽快到手机端付款！<<<<<<')
            notify.send_text(DamaiConfig.SERVERCHAN_SENDKEY,
                             '大麦抢票成功', '请尽快到手机端付款！')
        else:
            logger.warning('下单流程结束，未获取到订单信息')
            notify.send_text(DamaiConfig.SERVERCHAN_SENDKEY,
                             '大麦抢票流程结束', '下单流程结束，未获取到订单信息')
    return 0


def _fmt_local(ts: float, offset: float) -> str:
    """格式化时间戳为本地可读时间（含 NTP 偏移修正）。"""
    return time.strftime('%H:%M:%S', time.localtime(ts - offset))


def main() -> int:
    parser = argparse.ArgumentParser(prog='damai', description='大麦抢票模块')
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('login', help='扫码登录并保存登录态')
    subparsers.add_parser('reserve',
                          help='开抢前预约抢票（选票档/数量/观演人并提交抢票预约）')
    subparsers.add_parser('grab', help='加载登录态，开抢前预取并定时下单')
    args = parser.parse_args()

    try:
        if args.command == 'login':
            return cmd_login()
        if args.command == 'reserve':
            return cmd_reserve()
        return cmd_grab()
    except ValueError as e:
        logger.error('%s', e)
        return 1
    except KeyboardInterrupt:
        logger.warning('收到键盘中断(Ctrl+C)，已退出')
        return 130


if __name__ == '__main__':
    sys.exit(main())
