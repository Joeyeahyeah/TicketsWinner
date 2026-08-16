import os
import random
import string
import time

from dotenv import load_dotenv

load_dotenv()


class WeixinMiniAppConfig:
    # 基础配置
    APP_ID = os.getenv("WECHAT_APP_ID")
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
    APP_VERSION = os.getenv("APP_VERSION", "4.40.1")

    # 业务配置
    PROVINCE_CITY_ID = os.getenv("PROVINCE_CITY_ID", "BL1034")
    LOCATION_CITY_ID = os.getenv("LOCATION_CITY_ID", "1101")
    MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", 200))
    SALE_START_TIME = os.getenv("SALE_START_TIME", "18:00:00")

    # 票价配置（元），从预填信息无法可靠获取时可手动指定
    TICKET_PRICE = os.getenv("TICKET_PRICE", "280.00")
    PRICE_DISPLAY = os.getenv("PRICE_DISPLAY", "￥280")

    # 请求控制
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", 3))
    RETRY_INTERVAL_MIN = float(os.getenv("RETRY_INTERVAL_MIN", 0.15))
    RETRY_INTERVAL_MAX = float(os.getenv("RETRY_INTERVAL_MAX", 0.4))

    @classmethod
    def validate(cls):
        """启动前校验必需配置"""
        missing = []
        if not cls.APP_ID:
            missing.append("WECHAT_APP_ID")
        if not cls.ACCESS_TOKEN:
            missing.append("ACCESS_TOKEN")
        if missing:
            raise ValueError(f"缺少必需配置项: {', '.join(missing)}，请检查 .env 文件")

    @staticmethod
    def generate_front_trace_id():
        """生成唯一跟踪ID"""
        timestamp = int(time.time() * 1000)
        timestamp_base36 = WeixinMiniAppConfig._to_base36(timestamp)
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=11))
        return timestamp_base36 + random_str

    @staticmethod
    def _to_base36(number):
        """数字转base36"""
        alphabet = string.digits + string.ascii_lowercase
        if number == 0:
            return alphabet[0]
        base36 = ''
        while number:
            number, index = divmod(number, 36)
            base36 = alphabet[index] + base36
        return base36
