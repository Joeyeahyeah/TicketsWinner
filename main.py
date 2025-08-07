import requests
import time
import random
from config import Config

# -------- 请求1. 获取front-trace-id --------
# def base36(num):
#     alphabet = string.digits + string.ascii_lowercase
#     if num == 0:
#         return alphabet[0]
#     base36 = ''
#     while num:
#         num, i = divmod(num, 36)
#         base36 = alphabet[i] + base36
#     return base36
#
#
# def get_front_trace_id():
#     timestamp = int(time.time() * 1000)
#     timestamp_base36 = base36(timestamp)
#     random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=11))
#     return timestamp_base36 + random_str


# -------- 请求1. 获取front-trace-id --------


# -------- 请求2. 获取抢票预填信息 --------
# 添加ver参数
def get_prefilledlist(access_token, ver):
    url = 'https://65373d6e95c3170001074c57.caiyicloud.com/cyy_gatewayapi/show/buyer/v3/pre_filed_info/676d5b8c3958580001b70179'
    headers = {
        "Host": "65373d6e95c3170001074c57.caiyicloud.com",
        "Connection": "keep-alive",
        "terminal-src": "WEIXIN_MINI",
        "content-type": "application/json",
        "src": "weixin_mini",
        "ver": ver,
        "access-token": access_token,
        "merchant-id": "65373d6e95c3170001074c57",
        "front-trace-id": Config.get_front_trace_id(),
        "Accept-Encoding": "gzip,compress,br,deflate",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.53(0x1800352e) NetType/4G Language/zh_CN",
        "Referer": f"https://servicewechat.com/{Config.APP_ID}/42/page-frame.html"
    }
    params = {
        "needDetails": "true",
        "source": "FROM_SHOW_DETAIL_PRE_FILED",
        "src": "weixin_mini",
        "merchantId": "65373d6e95c3170001074c57",
        "ver": ver,
        "appId": Config.APP_ID
    }
    # 使用正确的GET参数传递方式
    res = requests.get(url=url, headers=headers, params=params)
    try:
        prefilledlist = res.json()['data']
        return (
            prefilledlist['preFiledId'],
            prefilledlist['userAudienceIds'][0],
            prefilledlist['bizSeatPlanId'],
            prefilledlist['bizShowId'],
            prefilledlist['bizShowSessionId']
        )
    except:
        print("获取预填信息失败，请检查网络或参数")
        return None, None, None, None, None


# -------- 请求2. 获取抢票预填信息 --------

# -------- 请求3. 获取抢票信息 --------
def get_ticket(ver, bsCityId, locationCityId, preFiledId, audienceId, skuId, showId, sessionId, access_token,
               ticketItems_id):
    url = 'https://65373d6e95c3170001074c57.caiyicloud.com/cyy_gatewayapi/trade/buyer/order/v5/create_order'
    headers = {
        "Host": "65373d6e95c3170001074c57.caiyicloud.com",
        "Connection": "keep-alive",
        "terminal-src": "WEIXIN_MINI",
        "content-type": "application/json",
        "src": "weixin_mini",
        "ver": ver,
        "access-token": access_token,
        "merchant-id": "65373d6e95c3170001074c57",
        "front-trace-id": Config.get_front_trace_id(),
        "Accept-Encoding": "gzip,compress,br,deflate",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.53(0x1800352e) NetType/4G Language/zh_CN",
        "Referer": f"https://servicewechat.com/{Config.APP_ID}/42/page-frame.html"
    }
    data = {
        "locationParam": {"bsCityId": bsCityId, "locationCityId": locationCityId},
        "preFiledId": preFiledId,
        "priceItemParam": [{
            "applyTickets": [],
            "priceItemType": "TICKET_FEE",
            "priceItemSpecies": "SEAT_PLAN",
            "priceItemVal": "280.00",
            "priceDisplay": "￥280",
            "priceItemName": "票款总额",
            "direction": "INCREASE"
        }],
        "merchantId": "65373d6e95c3170001074c57",
        "src": "weixin_mini",
        "appId": Config.APP_ID,
        "priorityId": "",
        "orderSource": "COMMON",
        "addressParam": {},
        "many2OneAudience": {},
        "ver": ver,
        "items": [{
            "sku": {
                "ticketItems": [{"id": ticketItems_id, "audienceId": audienceId}],
                "ticketPrice": "280.00",
                "skuId": skuId,
                "qty": 1,
                "skuType": "SINGLE"
            },
            "spu": {
                "addPromoVersionHash": "EMPTY_PROMOTION_HASH",
                "promotionVersionHash": "EMPTY_PROMOTION_HASH",
                "showId": showId,
                "sessionId": sessionId
            },
            "deliverMethod": "E_TICKET"
        }],
        "paymentParam": {
            "totalAmount": "280.00",
            "payAmount": "280.00"
        },
        "addPurchasePromotionId": ""
    }
    return requests.post(url=url, headers=headers, json=data)


# -------- 请求3. 获取抢票信息 --------

# -------- !!!!!!!! 抢票 !!!!!!!! --------
def run():
    print('>>>>>程序已启动>>>>>')

    # 添加ver参数
    preFiledId, audienceId, skuId, showId, sessionId = get_prefilledlist(
        Config.ACCESS_TOKEN,
        Config.VER
    )

    if not all([preFiledId, audienceId, skuId, showId, sessionId]):
        print(">>>>>获取预填信息失败，程序退出！>>>>>")
        return

    print(
        f'>>>>>获取预填信息成功>>>>>preFiledId: {preFiledId}>>>audienceId: {audienceId}>>>skuId: {skuId}>>>showId: {showId}>>>sessionId: {sessionId}>>>')

    # 精确时间控制
    today = time.strftime('%Y-%m-%d', time.localtime())
    target_time = time.mktime(time.strptime(f"{today} {start_time}", '%Y-%m-%d %H:%M:%S'))
    print(f"等待开抢时间: {today} {start_time}")

    while True:
        current_time = time.time()
        if current_time >= target_time:
            print(f'任务启动时间: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}')
            break
        # 动态调整等待时间
        sleep_time = min(0.1, target_time - current_time)
        if sleep_time > 0:
            time.sleep(sleep_time)

    # 生成ticketItems_id
    ticketItems_id = f"{int(time.time() * 1000) + random.randint(50, 80)}100000008"

    requests_times = 0
    while requests_times < max_requests_times:
        try:
            requests_times += 1
            res = get_ticket(ver, bsCityId, locationCityId, preFiledId, audienceId,
                             skuId, showId, sessionId, access_token, ticketItems_id)

            print(
                f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} >>> 请求次数: {requests_times} >>> {res.text[:100]}...")

            res_json = res.json()
            if res_json.get("comments") in ["正在为您自动尝试", "该演出还未开售"]:
                time.sleep(0.3)  # 减少等待时间
            elif res_json.get("comments") == "成功":
                print(">>>>>>抢票成功！请尽快到手机端付款！<<<<<<")
                break
        except Exception as e:
            print(f'请求出错: {e}')
            time.sleep(0.5)  # 出错后短暂等待

    if requests_times >= max_requests_times:
        print('超过最大请求次数，程序退出！')


# -------- !!!!!!!! 抢票 !!!!!!!! --------

if __name__ == '__main__':
    # 配置参数
    start_time = Config.START_TIME  # 抢票开始时间
    ver = Config.VER  # 当前版本
    bsCityId = Config.BS_CITY_ID  # 省份ID
    locationCityId = Config.LOCATION_CITY_ID # 城市ID
    access_token = Config.ACCESS_TOKEN  # 当前版本
    max_requests_times = Config.MAX_REQUESTS  # 最大请求次数
    # 启动抢票
    run()
