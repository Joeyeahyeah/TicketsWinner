import os
from pathlib import Path

from dotenv import load_dotenv

DAMAI_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=DAMAI_DIR / '.env')


class DamaiConfig:
    # 业务配置
    ITEM_URL = os.getenv("DAMAI_ITEM_URL")  # 演出详情页 URL
    SALE_START_TIME = os.getenv("SALE_START_TIME", "18:00:00")

    # 大麦 mtop 接口版本号（占位，待真机抓包确认，见 core/order.py）
    API_VERSION = os.getenv("DAMAI_API_VERSION", "1.0")

    # 登录态持久化路径（cookie + localStorage）
    STORAGE_STATE_PATH = os.getenv(
        "STORAGE_STATE_PATH", str(DAMAI_DIR / '.auth' / 'storage_state.json'))

    # 浏览器配置（抢票时可无头，登录时必须 headless=False）
    HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

    # Server酱推送（微信通知，可选）
    SERVERCHAN_SENDKEY = os.getenv("SERVERCHAN_SENDKEY")

    # 请求控制
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", 3))
    RETRY_INTERVAL_MIN = float(os.getenv("RETRY_INTERVAL_MIN", 0.15))
    RETRY_INTERVAL_MAX = float(os.getenv("RETRY_INTERVAL_MAX", 0.4))
    MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", 200))

    # 登录等待超时（秒）与滑块截图目录
    LOGIN_TIMEOUT = int(os.getenv("LOGIN_TIMEOUT", 180))
    SCREENSHOT_DIR = DAMAI_DIR / 'screenshots'

    @classmethod
    def validate(cls):
        """抢票启动前校验必需配置"""
        missing = []
        if not cls.ITEM_URL:
            missing.append("DAMAI_ITEM_URL")
        if missing:
            raise ValueError(f"缺少必需配置项: {', '.join(missing)}，请检查 damai/.env 文件")
