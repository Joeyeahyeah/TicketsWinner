"""playwright-stealth 薄封装：对上下文应用反指纹注入。

如需补充手写注入（navigator.webdriver / plugins / chrome / permissions 等），
在此模块扩展，保持调用方单入口。
"""
import logging

from playwright.sync_api import BrowserContext

logger = logging.getLogger('damai.browser.stealth')


def apply_stealth(context: BrowserContext) -> None:
    """对上下文及其后续新建页面应用 stealth（playwright-stealth 2.x API）"""
    try:
        from playwright_stealth import Stealth
    except ImportError as e:
        raise RuntimeError(
            '未安装 playwright-stealth 2.x，请执行: pip install "playwright-stealth~=2.0"') from e

    # 语言覆盖为中文，更贴近大麦真实用户环境
    Stealth(navigator_languages_override=('zh-CN', 'zh')).apply_stealth_sync(context)
    logger.debug('已对浏览器上下文应用 playwright-stealth')
