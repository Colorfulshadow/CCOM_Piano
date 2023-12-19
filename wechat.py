import threading
import time
import itchat
import re
from client import Client
from datetime import datetime, timedelta, timezone
from config import config
from caltime import SendTimeCalculator, TimeUtils
from main import AsyncPostSender

@itchat.msg_register('Text')
def choseroom(user ,start_time,end_time,room_name):
    sender = AsyncPostSender('2130', room_name, start_time, end_time, 30)
    start_segment_time = timestamp_to_utc8(start_time/1000)
    end_segment_time = timestamp_to_utc8(end_time/1000)
    success, message = sender.run()
    if success:
        itchat.send(u'{}成功选上时间段: \n{}-{}'.format(room_name, start_segment_time, end_segment_time), toUserName=user)
    else:
        itchat.send(u'{}时间段: \n{}\n{}\n选择失败\n原因：{}'.format(room_name, start_segment_time, end_segment_time, message), toUserName=user)

def run_choseroom_in_thread(user, start_time, end_time, room_name):
    # 在新线程中运行 choseroom 函数
    timeutils = TimeUtils()
    segments = timeutils.split_time(start_time, end_time, 3)
    for start_segment, end_segment in segments:
        thread = threading.Thread(target=choseroom, args=(user, start_segment, end_segment, room_name))
        thread.start()

def timestamp_to_utc8(timestamp):
    # 将时间戳转换为datetime对象
    dt = datetime.fromtimestamp(timestamp, timezone.utc)
    # 定义UTC+8时区
    utc_8 = timezone(timedelta(hours=8))
    # 将时间转换为UTC+8时区
    dt_utc_8 = dt.astimezone(utc_8)
    formatted_str = dt_utc_8.strftime('%Y-%m-%d %H:%M')
    return formatted_str

@itchat.msg_register('Text')
def text_reply(msg):
    match = re.match(r"选(\d{4})-(\d{4})([^\s]+)", msg['Text'])
    if match:
        start_time = match.group(1)
        end_time = match.group(2)
        room_name = match.group(3)
        run_choseroom_in_thread(msg.fromUserName,start_time, end_time, room_name)
        return u'已接收到房间{}预定请求{}-{}'.format(room_name,start_time,end_time)
    elif u'选琴房' in msg['Text']:
        return u'选择琴房格式为：\n\n"选<开始时间>-<结束时间><琴房名称>"\n\n例如：\n选择8:30到12:30的琴810, 输入\n\n"选0830-1230琴810"'
    # The existing conditions and responses

# @itchat.msg_register(['Picture', 'Recording', 'Attachment', 'Video'])
# def atta_reply(msg):
#     return ({ 'Picture': u'图片', 'Recording': u'录音',
#         'Attachment': u'附件', 'Video': u'视频', }.get(msg['Type']) +
#         u'已下载到本地') # download function is: msg['Text'](msg['FileName'])
#
# @itchat.msg_register(['Map', 'Card', 'Note', 'Sharing'])
# def mm_reply(msg):
#     if msg['Type'] == 'Map':
#         return u'收到位置分享'
#     elif msg['Type'] == 'Sharing':
#         return u'收到分享' + msg['Text']
#     elif msg['Type'] == 'Note':
#         return u'收到：' + msg['Text']
#     elif msg['Type'] == 'Card':
#         return u'收到好友信息：' + msg['Text']['Alias']
#
# @itchat.msg_register('Text', isGroupChat = True)
# def group_reply(msg):
#     if msg['isAt']:
#         return u'@%s\u2005%s' % (msg['ActualNickName'],
#             get_response(msg['Text']) or u'收到：' + msg['Text'])
#
# @itchat.msg_register('Friends')
# def add_friend(msg):
#     itchat.add_friend(**msg['Text'])
#     itchat.send_msg(u'项目主页：github.com/littlecodersh/ItChat\n'
#         + u'源代码  ：回复源代码\n' + u'图片获取：回复获取图片\n'
#         + u'欢迎Star我的项目关注更新！', msg['RecommendInfo']['UserName'])

itchat.auto_login(hotReload=True)
itchat.run()