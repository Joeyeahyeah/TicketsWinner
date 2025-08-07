import os
from dotenv import load_dotenv
import time
import string
import random

load_dotenv()  # 加载.env文件


class Config:
    # 基础配置
    APP_ID = os.getenv("WECHAT_APP_ID")
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
    VER = os.getenv("VER", "4.40.1")  # 带默认值

    # 业务配置
    BS_CITY_ID = os.getenv("BS_CITY_ID", 'BL1034')
    LOCATION_CITY_ID = os.getenv("LOCATION_CITY_ID", '1101')
    MAX_REQUESTS = int(os.getenv("MAX_REQUESTS", 200))
    START_TIME = os.getenv("START_TIME", "18:00:00")

    # -------- 请求1. 获取front-trace-id --------
    @staticmethod
    def get_front_trace_id():
        """生成唯一跟踪ID"""
        timestamp = int(time.time() * 1000)
        timestamp_base36 = Config._base36(timestamp)
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=11))
        return timestamp_base36 + random_str

    @staticmethod
    def _base36(num):
        """私有方法：数字转base36"""
        alphabet = string.digits + string.ascii_lowercase
        if num == 0:
            return alphabet[0]
        base36 = ''
        while num:
            num, i = divmod(num, 36)
            base36 = alphabet[i] + base36
        return base36
    # -------- 请求1. 获取front-trace-id --------