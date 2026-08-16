"""定时调度：NTP 校时 + 精确等待到开抢时间"""
import logging
import socket
import struct
import time

logger = logging.getLogger('damai.core.scheduler')

NTP_SERVER = 'ntp.aliyun.com'
NTP_PORT = 123
NTP_DELTA = 2208988800  # 1900 纪元与 1970 纪元的秒数差


def get_ntp_offset(timeout: float = 3) -> float:
    """请求 NTP 服务器，返回「服务器时间 - 本地时间」的偏移量（秒）"""
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(timeout)
    try:
        client.sendto(b'\x1b' + 47 * b'\0', (NTP_SERVER, NTP_PORT))
        data, _ = client.recvfrom(1024)
        # Transmit Timestamp：第 10 个 32 位无符号整数（秒部分）
        transmit_seconds = struct.unpack('!12I', data)[10]
        return (transmit_seconds - NTP_DELTA) - time.time()
    finally:
        client.close()


def calibrate_clock(timeout: float = 3) -> float:
    """校时，返回时钟偏移量；失败降级为本地时间（偏移 0）并告警"""
    try:
        offset = get_ntp_offset(timeout=timeout)
        logger.info('NTP 校时成功（%s），本地时钟偏移 %.3f 秒', NTP_SERVER, offset)
        return offset
    except (socket.error, struct.error, IndexError) as e:
        logger.warning('NTP 校时失败: %s，降级使用本地时间', e)
        return 0.0


def target_timestamp(sale_start_time: str) -> float:
    """今日 SALE_START_TIME 对应的本地时间戳"""
    today = time.strftime('%Y-%m-%d', time.localtime())
    return time.mktime(time.strptime(f'{today} {sale_start_time}', '%Y-%m-%d %H:%M:%S'))


def wait_until_start_time(target_ts: float, offset: float = 0.0):
    """精确等待到目标时间（基于 NTP 偏移修正），动态缩短睡眠间隔"""
    while True:
        remaining = target_ts - (time.time() + offset)
        if remaining <= 0:
            break
        time.sleep(min(0.1, remaining))
