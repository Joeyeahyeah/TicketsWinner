import logging

from weixin_mini_app import WeixinMiniAppConfig, grab_tickets

logger = logging.getLogger('tickets_winner')

if __name__ == '__main__':
    try:
        grab_tickets(WeixinMiniAppConfig)
    except KeyboardInterrupt:
        print('\n已手动终止程序。')
    except ValueError as e:
        logger.error('启动失败: %s', e)
        raise SystemExit(1)
