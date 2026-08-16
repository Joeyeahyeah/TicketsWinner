"""大麦抢票模块入口

用法:
    python -m damai.main login     # 扫码登录，保存 storage_state（抢票前一天执行）
    python -m damai.main reserve   # 开抢前预约抢票：选票档/数量/观演人并提交抢票预约
    python -m damai.main grab      # 加载登录态，开抢前预取，到达开抢时间后下单

大麦预约抢票机制（2024-2025 实测有效）：
- 开抢前详情页主按钮文案为「预约抢票」，用户需提前预约想看的票档/数量
- 倒计时归零时按钮变为「立即抢票」，点击后自动勾选已预约内容直跳确认订单页
- grab 流程在开抢前 N 秒（GET_SKU_BEFORE_START）走预约入口进入确认订单页预取
  真实 skuId/buyerIds，开抢瞬间直接发起 mtop 下单，跳过详情页逐项选择
"""
import argparse
import logging
import sys

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


def _prefetch_sku_before_start(page, config) -> None:
    """开抢前预取阶段：走预约入口进入确认订单页，预取真实 skuId/buyerIds 缓存。

    - 优先读 reserve_state.json 本地缓存（reserve 子命令已写入）
    - 页面预取作为验证/兜底：从确认订单页 __INITIAL_STATE__ 取 skuId
    - 预取到的值回填到 config 实例属性，供 order.create_order 复用
    - 失败时降级（config 保留原值或空），order._resolve_sku_id 兜底
    """
    from .core import reserve

    state = reserve.load_reserve_state(config)
    cached_sku = state.get('skuId', '')
    cached_buyers = state.get('buyerIds', [])

    # 回填缓存到 config 实例属性（类属性是只读的，用实例属性覆盖读取逻辑）
    if cached_sku and not config.SKU_ID:
        config.SKU_ID = cached_sku
        logger.info('预取: 从预约缓存读到 skuId=%s', cached_sku)
    if cached_buyers and not config.get_buyer_ids():
        config.BUYER_IDS = ','.join(cached_buyers)
        logger.info('预取: 从预约缓存读到 buyerIds=%s', cached_buyers)

    # 页面预取作为兜底（确认订单页上下文更可靠）
    page_sku = ''
    try:
        page_sku = page.evaluate("""
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
        page_sku = str(page_sku or '').strip()
    except Exception as e:  # noqa: BLE001
        logger.warning('预取: 页面探测 skuId 异常: %s', e)

    if page_sku and not config.SKU_ID:
        config.SKU_ID = page_sku
        logger.info('预取: 从页面探测到 skuId=%s', page_sku)
    elif page_sku and config.SKU_ID and page_sku != config.SKU_ID:
        logger.warning('预取: 页面 skuId=%s 与缓存 %s 不一致，以页面为准',
                       page_sku, config.SKU_ID)
        config.SKU_ID = page_sku

    if not config.SKU_ID:
        logger.warning('预取: 仍未取到 skuId，开抢时将由 order._resolve_sku_id 兜底')


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
        logger.info('进入预取阶段')
        try:
            # 走「立即抢票」入口（开抢前按钮文案可能仍是「预约抢票」，
            # 但点击后大麦会引导进入预约/确认订单页，具体抓包后微调）
            from .core.reserve import _try_click
            _try_click(page, DamaiConfig.BUY_NOW_SELECTOR, '立即抢票入口',
                       timeout=3)
            _prefetch_sku_before_start(page, DamaiConfig)
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
    import time
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
