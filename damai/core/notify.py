"""Server酱推送：抢票结果与风控滑块截图通知。

推送失败仅记录日志，不中断抢票主流程。
"""
import base64
import logging
from pathlib import Path

import requests

logger = logging.getLogger('damai.core.notify')

API_TEMPLATE = 'https://sctapi.ftqq.com/{sendkey}.send'


def _post(sendkey: str, data: dict, timeout: float) -> None:
    try:
        response = requests.post(
            API_TEMPLATE.format(sendkey=sendkey), data=data, timeout=timeout)
        if response.status_code != 200:
            logger.warning('Server酱推送返回 status=%d: %s',
                           response.status_code, response.text[:200])
    except requests.RequestException as e:
        logger.error('Server酱推送失败: %s', e)


def send_text(sendkey: str, title: str, content: str = '', timeout: float = 3) -> None:
    """发送文本通知（content 支持 markdown）"""
    if not sendkey:
        logger.warning('未配置 SERVERCHAN_SENDKEY，跳过推送: %s', title)
        return
    _post(sendkey, {'title': title, 'desp': content}, timeout)


def send_screenshot(sendkey: str, image_path, title: str = '触发风控验证，请尽快人工处理',
                    timeout: float = 10) -> None:
    """推送滑块截图到手机（base64 内联 markdown 图片）。

    注: Server酱对 base64 图片的渲染依赖客户端支持，若无法显示可改为先传图床再发 URL。
    """
    if not sendkey:
        logger.warning('未配置 SERVERCHAN_SENDKEY，跳过截图推送: %s', image_path)
        return
    path = Path(image_path)
    if not path.exists():
        logger.error('截图文件不存在: %s', path)
        return
    try:
        encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    except OSError as e:
        logger.error('读取截图失败: %s', e)
        return
    content = f'![screenshot](data:image/png;base64,{encoded})'
    _post(sendkey, {'title': title, 'desp': content}, timeout)
