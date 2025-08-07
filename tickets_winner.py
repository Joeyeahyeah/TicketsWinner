import requests
import time
import execjs
import random


# # 源码函数1 #号后面的是注释，起解释说明作用
# def funtion_1():
#     # 函数具体内容省略
#     return value_1
#
#
# # 源码函数2，假设有一个参数
# def funtion_2(arg1):
#     # 函数具体内容省略
#     return value_2
#
#
# # 源码函数3，假设提交抢票请求的函数，假设有两个参数，
# def funtion_3(arg1, arg2):
#     # 函数具体内容省略
#     return res


# 主函数，也就是启动函数，在这里将其他函数串起来，***这是本文重点***
# def run():
#     # 调用funtion_1，获取返回值value_1
#     value_1 = funtion_1()
#     # 调用funtion_2，获取返回值value_2，注意：将value_1传参给funtion_2
#     value_2 = funtion_2(value_1)
# 
#     # ***以下代码是时间控制器，控制到规定时间才提交抢票请求，否则就一直等待***
#     round_num = 0
#     while True:
#         if time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())[-8:] >= start_time:
#             print('任务启动时间：', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
#             break
#         time.sleep(0.1)
#         round_num += 1
#         if round_num % 600 == 0:
#             print('等待中...：', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
#     # ***以上代码是时间控制器，控制到规定时间才提交抢票请求，否则就一直等待***
# 
#     # ***以下代码是提交抢票请求，为了提高成功率，我加了控制逻辑***
#     requests_times = 0
#     while True:
#         if requests_times >= max_requests_times:
#             print('超过自定义最大请求次数，程序退出！')
#             break
#         try:
#             requests_times += 1
#             # 调用funtion_3，也就是提交抢票请求，获取返回值res，注意：将value_1和value_2传参给funtion_3，这就叫串起来
#             res = funtion_3(arg1, arg2)
#             print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), '>>>', res.text)
#             res_json = res.json()
#             if res_json["comments"] == "成功":
#                 print('抢票成功，请及时付款，超时订单自动取消')
#                 break
#         except Exception as e:
#             print('请求出错，时间：', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), e)
#             break


def get_prefilledlist(access_token):
    pass


def get_ticket(ver, bsCityId, locationCityId, preFiledId, audienceId, skuId, showId, sessionId, access_token,
               ticketItems_id):
    pass


def run(ver=None, bsCityId=None, locationCityId=None):
    print('>>>>>程序已启动>>>>>')
    prefilledlist = get_prefilledlist(access_token)
    preFiledId = prefilledlist['preFiledId']
    audienceId = prefilledlist['userAudienceIds'][0]
    skuId = prefilledlist['bizSeatPlanId']
    showId = prefilledlist['bizShowId']
    sessionId = prefilledlist['bizShowSessionId']
    print('>>>>>获取预填信息成功>>>>>preFiledId：%s>>>audienceId：%s>>>skuId：%s>>>showId：%s>>>sessionId：%s>>>' % (
        preFiledId, audienceId, skuId, showId, sessionId))
    round_num = 0
    while True:
        if time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())[-8:] >= start_time:
            print('任务启动时间：', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            break
        time.sleep(0.2)
        round_num += 1
        if round_num % 600 == 0:
            print('等待中...：', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
    requests_times = 0
    # 整6点生成ticketItems_id
    ticketItems_id = str(int(time.time() * 1000) + random.randint(50, 80)) + '100000008'
    while True:
        if requests_times >= max_requests_times:
            print('超过自定义最大请求次数，程序退出！')
            break
        try:
            # 正式发起请求
            requests_times += 1
            res = get_ticket(ver, bsCityId, locationCityId, preFiledId, audienceId, skuId, showId, sessionId,
                             access_token, ticketItems_id)
            print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), '>>>', res.text)
            res_json = res.json()
            if res_json["comments"] == "正在为您自动尝试" or res_json["comments"] == "该演出还未开售":
                time.sleep(1)  # 系统默认3秒重复一次请求
            elif res_json["comments"] == "成功":
                break
        except Exception as e:
            print('请求出错，时间：', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), e)
            break

# 启动程序之前要准备的参数
if __name__ == '__main__':
    start_time = '18:00:00'  # 抢票开始时间
    ver = "4.20.2"
    bsCityId = "BL1034"  # 默认北京，最好换成自己的
    locationCityId = "1101"  # 默认北京，最好换成自己的
    # access_token每次抢票前两小时修改成最新的
    access_token = "your token"
    max_requests_times = 3  # 设置最多请求3次，如果请求3次还没抢到说明这次希望不大了
    run()


