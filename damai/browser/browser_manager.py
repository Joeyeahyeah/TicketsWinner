"""Playwright 浏览器生命周期管理"""
import logging
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

from ..config import DamaiConfig
from .stealth import apply_stealth

logger = logging.getLogger('damai.browser')


@contextmanager
def browser_session(config: DamaiConfig = DamaiConfig, use_storage_state: bool = True,
                    headless: bool = None):
    """浏览器会话上下文管理器，确保异常/中断时释放资源。

    :param config: 配置对象
    :param use_storage_state: 是否加载已保存的登录态
    :param headless: 覆盖配置中的 HEADLESS（登录时强制 False）
    """
    if headless is None:
        headless = config.HEADLESS

    playwright = sync_playwright().start()
    browser = None
    try:
        browser = playwright.chromium.launch(headless=headless)
        context_options = {}
        storage_path = Path(config.STORAGE_STATE_PATH)
        if use_storage_state:
            if storage_path.exists():
                context_options['storage_state'] = str(storage_path)
                logger.info('已加载登录态: %s', storage_path)
            else:
                logger.warning('登录态文件不存在: %s，请先运行 python -m damai.main login',
                               storage_path)
        context = browser.new_context(**context_options)
        apply_stealth(context)
        yield context
    finally:
        # 浏览器可能已被手动关闭（TargetClosedError）或连接已断开，
        # 清理动作不应再抛异常掩盖主流程的退出
        try:
            if browser is not None and browser.is_connected():
                browser.close()
        except Exception as e:  # noqa: BLE001 - 清理阶段的异常降级为告警
            logger.warning('关闭浏览器异常（可忽略）: %s', e)
        try:
            playwright.stop()
        except Exception as e:  # noqa: BLE001
            logger.warning('停止 playwright 异常（可忽略）: %s', e)
