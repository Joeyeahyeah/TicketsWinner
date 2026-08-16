"""大麦抢票模块入口

用法:
    python -m damai.main login   # 扫码登录，保存 storage_state（抢票前一天执行）
    python -m damai.main grab    # 加载登录态，定时等待并在页面 JS 环境调用 mtop 下单
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


def cmd_grab() -> int:
    DamaiConfig.validate()

    from .browser.browser_manager import browser_session
    from .core import notify, order, scheduler

    offset = scheduler.calibrate_clock(timeout=DamaiConfig.REQUEST_TIMEOUT)
    target_ts = scheduler.target_timestamp(DamaiConfig.SALE_START_TIME)

    with browser_session(DamaiConfig) as context:
        page = context.new_page()
        logger.info('打开演出详情页: %s', DamaiConfig.ITEM_URL)
        page.goto(DamaiConfig.ITEM_URL, timeout=int(DamaiConfig.REQUEST_TIMEOUT * 10000))

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


def main() -> int:
    parser = argparse.ArgumentParser(prog='damai', description='大麦抢票模块')
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('login', help='扫码登录并保存登录态')
    subparsers.add_parser('grab', help='加载登录态，定时等待并下单')
    args = parser.parse_args()

    try:
        if args.command == 'login':
            return cmd_login()
        return cmd_grab()
    except ValueError as e:
        logger.error('%s', e)
        return 1
    except KeyboardInterrupt:
        logger.warning('收到键盘中断(Ctrl+C)，已退出')
        return 130


if __name__ == '__main__':
    sys.exit(main())
