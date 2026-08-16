"""下单流程（占位）。

TODO: 大麦下单链路需真机/模拟器抓包确认后实现，要点：
- 接口: mtop.damai.buy.order.create（版本号走配置 DAMAI_API_VERSION，勿硬编码）
- 签名: 由页面内 JS 环境自动生成 mtop x-sign，通过 page.evaluate / 页面操作触发，
        不在 Python 侧逆向签名算法
- 风控: 触发滑块时截图 → Server酱推送 → 等待人工处理（不做自动化绕过）

参考 payload 模板（字段以实际抓包为准，版本号配置化）::

    {
        "api": "mtop.damai.buy.order.create",
        "v": "<DAMAI_API_VERSION>",
        "params": {
            "itemId": "<演出 itemId，从 DAMAI_ITEM_URL 解析>",
            "skuId": "<票档 skuId，抓包确认>",
            "quantity": 1,
            "buyerIds": ["<观演人 id，提前在账号中维护>"],
        },
    }
"""
import logging

logger = logging.getLogger('damai.core.order')


def create_order(page, config):
    """下单主流程（待实现）。

    :param page: 已加载登录态、已打开演出详情页的 Playwright Page
    :param config: DamaiConfig
    :return: 下单成功返回订单信息 dict，未实现/失败返回 None
    """
    logger.warning('下单流程尚未实现（接口版本号与请求体待真机抓包确认），'
                   '本次流程仅执行到开抢时间为止')
    return None
