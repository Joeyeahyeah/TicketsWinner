import logging
import random
import time

import requests

from .config import WeixinMiniAppConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('weixin_mini_app')

BASE_URL = 'https://65373d6e95c3170001074c57.caiyicloud.com'
MERCHANT_ID = '65373d6e95c3170001074c57'
USER_AGENT = ('Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) '
              'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 '
              'MicroMessenger/8.0.53(0x1800352e) NetType/4G Language/zh_CN')

RETRYABLE_COMMENTS = {"正在为您自动尝试", "该演出还未开售"}


def build_request_headers(access_token: str, app_version: str) -> dict:
    return {
        "Host": "65373d6e95c3170001074c57.caiyicloud.com",
        "Connection": "keep-alive",
        "terminal-src": "WEIXIN_MINI",
        "content-type": "application/json",
        "src": "weixin_mini",
        "ver": app_version,
        "access-token": access_token,
        "merchant-id": MERCHANT_ID,
        "front-trace-id": WeixinMiniAppConfig.generate_front_trace_id(),
        "Accept-Encoding": "gzip,compress,br,deflate",
        "User-Agent": USER_AGENT,
        "Referer": f"https://servicewechat.com/{WeixinMiniAppConfig.APP_ID}/42/page-frame.html",
    }


def fetch_prefilled_info(access_token: str, app_version: str):
    """获取抢票预填信息，返回关键 ID 五元组"""
    url = f'{BASE_URL}/cyy_gatewayapi/show/buyer/v3/pre_filed_info/676d5b8c3958580001b70179'
    params = {
        "needDetails": "true",
        "source": "FROM_SHOW_DETAIL_PRE_FILED",
        "src": "weixin_mini",
        "merchantId": MERCHANT_ID,
        "ver": app_version,
        "appId": WeixinMiniAppConfig.APP_ID,
    }
    try:
        response = requests.get(
            url=url,
            headers=build_request_headers(access_token, app_version),
            params=params,
            timeout=WeixinMiniAppConfig.REQUEST_TIMEOUT,
        )
        data = response.json()['data']
        return (
            data['preFiledId'],
            data['userAudienceIds'][0],
            data['bizSeatPlanId'],
            data['bizShowId'],
            data['bizShowSessionId'],
        )
    except requests.RequestException as e:
        logger.error("获取预填信息网络异常: %s", e)
    except (KeyError, ValueError) as e:
        logger.error("解析预填信息失败: %s", e)
        logger.error("响应内容: %s", getattr(response, 'text', '')[:300])
    return None


def build_order_payload(config: WeixinMiniAppConfig, province_city_id, location_city_id,
                        pre_filed_id, audience_id, seat_plan_id, show_id, session_id,
                        ticket_item_id) -> dict:
    price = config.TICKET_PRICE
    return {
        "locationParam": {"bsCityId": province_city_id, "locationCityId": location_city_id},
        "preFiledId": pre_filed_id,
        "priceItemParam": [{
            "applyTickets": [],
            "priceItemType": "TICKET_FEE",
            "priceItemSpecies": "SEAT_PLAN",
            "priceItemVal": price,
            "priceDisplay": config.PRICE_DISPLAY,
            "priceItemName": "票款总额",
            "direction": "INCREASE",
        }],
        "merchantId": MERCHANT_ID,
        "src": "weixin_mini",
        "appId": config.APP_ID,
        "priorityId": "",
        "orderSource": "COMMON",
        "addressParam": {},
        "many2OneAudience": {},
        "ver": config.APP_VERSION,
        "items": [{
            "sku": {
                "ticketItems": [{"id": ticket_item_id, "audienceId": audience_id}],
                "ticketPrice": price,
                "skuId": seat_plan_id,
                "qty": 1,
                "skuType": "SINGLE",
            },
            "spu": {
                "addPromoVersionHash": "EMPTY_PROMOTION_HASH",
                "promotionVersionHash": "EMPTY_PROMOTION_HASH",
                "showId": show_id,
                "sessionId": session_id,
            },
            "deliverMethod": "E_TICKET",
        }],
        "paymentParam": {"totalAmount": price, "payAmount": price},
        "addPurchasePromotionId": "",
    }


def submit_order_request(payload: dict, access_token: str, app_version: str):
    """创建订单（抢票）"""
    url = f'{BASE_URL}/cyy_gatewayapi/trade/buyer/order/v5/create_order'
    return requests.post(
        url=url,
        headers=build_request_headers(access_token, app_version),
        json=payload,
        timeout=WeixinMiniAppConfig.REQUEST_TIMEOUT,
    )


def generate_ticket_item_id() -> str:
    """生成 ticketItems_id：时间戳+随机偏移 拼接固定后缀，
    模拟客户端真实 ID 生成模式（后缀 100000008 对应该场次票档，换场次需抓包确认）"""
    return f"{int(time.time() * 1000) + random.randint(50, 80)}100000008"


def wait_until_start_time(target_timestamp: float):
    """精确等待到目标时间，动态缩短睡眠间隔"""
    while True:
        remaining = target_timestamp - time.time()
        if remaining <= 0:
            break
        time.sleep(min(0.1, remaining))


def grab_tickets(config: WeixinMiniAppConfig):
    logger.info('>>>>> 程序已启动 >>>>>')
    config.validate()

    prefilled_info = fetch_prefilled_info(config.ACCESS_TOKEN, config.APP_VERSION)
    if not prefilled_info:
        logger.error('>>>>> 获取预填信息失败，程序退出 >>>>>')
        return

    pre_filed_id, audience_id, seat_plan_id, show_id, session_id = prefilled_info
    logger.info('>>>>> 获取预填信息成功 >>>>>')
    logger.info('preFiledId=%s audienceId=%s seatPlanId=%s showId=%s sessionId=%s',
                pre_filed_id, audience_id, seat_plan_id, show_id, session_id)

    today = time.strftime('%Y-%m-%d', time.localtime())
    sale_start_timestamp = time.mktime(
        time.strptime(f"{today} {config.SALE_START_TIME}", '%Y-%m-%d %H:%M:%S'))
    logger.info('等待开抢时间: %s %s', today, config.SALE_START_TIME)
    wait_until_start_time(sale_start_timestamp)
    logger.info('任务启动时间: %s', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))

    ticket_item_id = generate_ticket_item_id()
    payload = build_order_payload(
        config, config.PROVINCE_CITY_ID, config.LOCATION_CITY_ID,
        pre_filed_id, audience_id, seat_plan_id, show_id, session_id, ticket_item_id,
    )

    for attempt_number in range(1, config.MAX_ATTEMPTS + 1):
        try:
            start = time.monotonic()
            response = submit_order_request(payload, config.ACCESS_TOKEN, config.APP_VERSION)
            elapsed_milliseconds = (time.monotonic() - start) * 1000

            try:
                response_json = response.json()
                comments = response_json.get("comments", "")
            except ValueError:
                logger.warning('请求%d 非JSON响应 status=%d: %s',
                               attempt_number, response.status_code, response.text[:100])
                time.sleep(random.uniform(config.RETRY_INTERVAL_MIN, config.RETRY_INTERVAL_MAX))
                continue

            logger.info('请求%d status=%d %.0fms comments=%s',
                        attempt_number, response.status_code, elapsed_milliseconds, comments)

            if comments == "成功":
                logger.info('>>>>>> 抢票成功！请尽快到手机端付款！<<<<<<')
                return
            if comments not in RETRYABLE_COMMENTS:
                logger.warning('未知提示: %s 响应: %s', comments, response.text[:200])

            time.sleep(random.uniform(config.RETRY_INTERVAL_MIN, config.RETRY_INTERVAL_MAX))
        except requests.RequestException as e:
            logger.error('请求%d 出错: %s', attempt_number, e)
            time.sleep(0.5)
        except KeyboardInterrupt:
            logger.warning('收到键盘中断(Ctrl+C)，已停止抢票（第 %d 次请求后）', attempt_number)
            raise

    logger.warning('超过最大请求次数(%d)，程序退出！', config.MAX_ATTEMPTS)
