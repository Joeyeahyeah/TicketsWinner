import os
from pathlib import Path

from dotenv import load_dotenv

DAMAI_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=DAMAI_DIR / '.env')


class DamaiConfig:
    # 业务配置
    ITEM_URL = os.getenv("DAMAI_ITEM_URL")  # 演出详情页 URL
    SALE_START_TIME = os.getenv("SALE_START_TIME", "18:00:00")

    # 大麦 mtop 接口版本号（占位，待真机抓包确认，见 core/order.py 与 docs/packet_capture.md）
    API_VERSION = os.getenv("DAMAI_API_VERSION", "1.0")

    # 下单配置（票档 skuId 与观演人，均待真机抓包确认后填入 .env）
    # skuId 留空时，order.py 会尝试在开抢前从详情页运行时获取（见 core/order.py）
    SKU_ID = os.getenv("SKU_ID", "")
    # 观演人 ID，逗号分隔；留空时尝试从页面确认订单上下文获取
    BUYER_IDS = os.getenv("BUYER_IDS", "")
    # 下单数量（默认 1）
    QUANTITY = int(os.getenv("QUANTITY", 1))

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

    # 滑块检测（选择器待真机抓包确认，见 docs/packet_capture.md 第 5.4 节）
    SLIDER_SELECTORS = [s.strip() for s in os.getenv(
        "SLIDER_SELECTORS",
        "iframe[id*=captcha], iframe[src*=punish], "
        "iframe[src*=ncaptcha], .captcha, .nc-container").split(",") if s.strip()]
    # 等待人工完成滑块的轮询超时（秒），避免无限阻塞
    SLIDER_WAIT_TIMEOUT = int(os.getenv("SLIDER_WAIT_TIMEOUT", 120))

    @classmethod
    def validate(cls):
        """抢票启动前校验必需配置"""
        missing = []
        if not cls.ITEM_URL:
            missing.append("DAMAI_ITEM_URL")
        if missing:
            raise ValueError(f"缺少必需配置项: {', '.join(missing)}，请检查 damai/.env 文件")

    @classmethod
    def get_buyer_ids(cls):
        """观演人 ID 列表（逗号分隔解析）"""
        return [b.strip() for b in cls.BUYER_IDS.split(",") if b.strip()]
