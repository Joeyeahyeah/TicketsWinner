"""大麦扫码登录：保存 storage_state 供抢票复用。

建议抢票前一天执行: python -m damai.main login
"""
import logging
import time
from pathlib import Path

from ..config import DamaiConfig
from .browser_manager import browser_session

logger = logging.getLogger('damai.browser.login')

LOGIN_URL = 'https://passport.damai.cn/login'

# 登录成功后由阿里系域名种下的鉴权 cookie（出现任一即视为已登录）
# 注: 若实际抓包发现判定不准，以真机验证后的 cookie 名为准
AUTH_COOKIE_NAMES = {'cookie2', '_nk_', 'munb'}


def login(config: DamaiConfig = DamaiConfig) -> bool:
    """打开登录页等待用户扫码，登录成功后保存 storage_state"""
    storage_path = Path(config.STORAGE_STATE_PATH)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    with browser_session(config, use_storage_state=False, headless=False) as context:
        page = context.new_page()
        page.goto(LOGIN_URL, timeout=int(config.REQUEST_TIMEOUT * 10000))
        print('请在打开的浏览器窗口中扫码登录大麦账号...')

        deadline = time.time() + config.LOGIN_TIMEOUT
        while time.time() < deadline:
            cookies = context.cookies()
            if any(c['name'] in AUTH_COOKIE_NAMES for c in cookies):
                context.storage_state(path=str(storage_path))
                logger.info('登录成功，登录态已保存: %s', storage_path)
                return True
            time.sleep(2)

    logger.error('等待登录超时（%d 秒），请重试', config.LOGIN_TIMEOUT)
    return False
