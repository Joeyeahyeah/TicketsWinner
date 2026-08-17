import os
from pathlib import Path

from dotenv import load_dotenv

DAMAI_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=DAMAI_DIR / '.env')


class DamaiConfig:
    # 业务配置
    ITEM_URL: str | None = os.getenv("DAMAI_ITEM_URL")  # 演出详情页 URL
    SALE_START_TIME: str = os.getenv("SALE_START_TIME", "18:00:00")

    # 大麦 mtop 下单接口名与版本号（抓包确认：接口名是 trade.order.create.h5）
    ORDER_API: str = os.getenv("DAMAI_ORDER_API", "mtop.damai.trade.order.create.h5")
    API_VERSION: str = os.getenv("DAMAI_API_VERSION", "1.0")

    # 下单配置（票档 skuId 与观演人，均待真机抓包确认后填入 .env）
    # skuId 留空时，order.py 会尝试在开抢前从详情页运行时获取（见 core/order.py）
    SKU_ID: str = os.getenv("SKU_ID", "")
    # 观演人 ID，逗号分隔；留空时尝试从页面确认订单上下文获取
    BUYER_IDS: str = os.getenv("BUYER_IDS", "")
    # 下单数量（默认 1）
    QUANTITY: int = int(os.getenv("QUANTITY", 1))

    # 登录态持久化路径（cookie + localStorage）
    STORAGE_STATE_PATH: str = os.getenv(
        "STORAGE_STATE_PATH", str(DAMAI_DIR / '.auth' / 'storage_state.json'))

    # 浏览器配置（抢票时可无头，登录时必须 headless=False）
    HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"

    # Server酱推送（微信通知，可选）
    SERVERCHAN_SENDKEY: str | None = os.getenv("SERVERCHAN_SENDKEY")

    # 请求控制
    REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", 3))
    RETRY_INTERVAL_MIN: float = float(os.getenv("RETRY_INTERVAL_MIN", 0.15))
    RETRY_INTERVAL_MAX: float = float(os.getenv("RETRY_INTERVAL_MAX", 0.4))
    MAX_ATTEMPTS: int = int(os.getenv("MAX_ATTEMPTS", 200))

    # 登录等待超时（秒）与滑块截图目录
    LOGIN_TIMEOUT: int = int(os.getenv("LOGIN_TIMEOUT", 180))
    SCREENSHOT_DIR: Path = DAMAI_DIR / 'screenshots'

    # 滑块检测（选择器待真机抓包确认，见 docs/packet_capture.md 第 5.4 节）
    SLIDER_SELECTORS: list[str] = [s.strip() for s in os.getenv(
        "SLIDER_SELECTORS",
        "iframe[id*=captcha], iframe[src*=punish], "
        "iframe[src*=ncaptcha], .captcha, .nc-container").split(",") if s.strip()]
    # 等待人工完成滑块的轮询超时（秒），避免无限阻塞
    SLIDER_WAIT_TIMEOUT: int = int(os.getenv("SLIDER_WAIT_TIMEOUT", 120))

    # ---------- 预约抢票机制（开抢前预选票档/数量/观演人）----------
    # 开抢前 N 秒进入「预取阶段」：走预约入口直跳确认订单页，预取真实 skuId/buyerIds 缓存
    # 避免开抢瞬间才发现取不到 skuId（详情页 JS 可能尚未挂载）
    GET_SKU_BEFORE_START: int = int(os.getenv("GET_SKU_BEFORE_START", 5))
    # 页面加载超时（秒），原 REQUEST_TIMEOUT*10000 是 30 秒疑似笔误，独立配置更直观
    PAGE_LOAD_TIMEOUT: int = int(os.getenv("PAGE_LOAD_TIMEOUT", 30))

    # 预约入口/立即抢票按钮选择器（均待真机抓包确认，见 docs/packet_capture.md 第 5.5 节）
    # 开抢前详情页主按钮文案为「预约抢票」，开抢后变为「立即抢票」
    # 默认空串：强制抓包后填入，避免默认值导致 validate_reserve 校验形同虚设
    RESERVE_SUBMIT_SELECTOR: str = os.getenv("RESERVE_SUBMIT_SELECTOR", "")
    # 开抢后详情页主按钮（点击后会自动勾选已预约票档/数量，直跳确认订单页）
    BUY_NOW_SELECTOR: str = os.getenv("BUY_NOW_SELECTOR", "")
    # 确认订单页「提交订单」按钮选择器（order.create_order 点击它触发下单）
    SUBMIT_ORDER_SELECTOR: str = os.getenv("SUBMIT_ORDER_SELECTOR", ".submit-btn, [class*=submit]")
    # 选票弹窗「确认」按钮选择器（详情页点主按钮后弹出选票弹窗，选完票价点确认进确认订单页）
    SKU_CONFIRM_SELECTOR: str = os.getenv("SKU_CONFIRM_SELECTOR", "")
    # 预约时票档/数量/观演人选择器，逗号分隔（具体抓包后填）
    RESERVE_SKU_SELECTOR: str = os.getenv("RESERVE_SKU_SELECTOR", "")
    RESERVE_QTY_SELECTOR: str = os.getenv("RESERVE_QTY_SELECTOR", "")
    RESERVE_BUYER_SELECTOR: str = os.getenv("RESERVE_BUYER_SELECTOR", "")

    # 预约状态持久化（grab 预取阶段可优先读本地缓存，页面预取作为验证/兜底）
    RESERVE_STATE_PATH: str = os.getenv(
        "RESERVE_STATE_PATH",
        str(DAMAI_DIR / '.auth' / 'reserve_state.json'))

    @classmethod
    def validate(cls):
        """抢票启动前校验必需配置"""
        missing = []
        if not cls.ITEM_URL:
            missing.append("DAMAI_ITEM_URL")
        if missing:
            raise ValueError(f"缺少必需配置项: {', '.join(missing)}，请检查 damai/.env 文件")

    @classmethod
    def validate_reserve(cls):
        """reserve 子命令校验：仅需详情页与预约入口选择器"""
        missing = []
        if not cls.ITEM_URL:
            missing.append("DAMAI_ITEM_URL")
        if not cls.RESERVE_SUBMIT_SELECTOR:
            missing.append("RESERVE_SUBMIT_SELECTOR")
        if missing:
            raise ValueError(
                f"预约缺少必需配置项: {', '.join(missing)}，请检查 damai/.env 文件")

    @classmethod
    def get_buyer_ids(cls):
        """观演人 ID 列表（逗号分隔解析）"""
        return [b.strip() for b in cls.BUYER_IDS.split(",") if b.strip()]
