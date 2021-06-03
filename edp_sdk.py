# coding: utf-8
import json
import socket
import struct
import sys
import time

import requests


HEART_BEAT = b'\xC0\x00'


def ts_print(*args, prefix='', end=''):
    t = time.strftime("[%Y-%m-%d %H:%M:%S]:")
    print(t, *args)


def _message_len(i):
    res = []
    while i > 0:
        temp = i % 128
        i = i // 128

        if i > 0:
            res.append(temp + 128)
        elif i == 0:
            res.append(temp)
    return bytes(res)


def calc_body_len(r_msg):
    res = []
    for x in range(4):
        if r_msg[x+1] > 128:
            res.append(r_msg[x+1] - 128)
        else:
            res.append(r_msg[x+1])
            break
        if x == 3 and r_msg[x+1] > 128:
            print('Error: Wrong body length！')
            return

    body_len = 0
    for x in range(len(res)):
        body_len += res[x] * 128**x
    return body_len, len(res)


def parse_body_len(data):
    rest_len = 0
    offset = 0
    for x in range(1, 5):
        temp = bin(data[x])[2:]
        if len(temp) == 8:
            rest_len += int(temp[1:].zfill(8), 2) * pow(128, x - 1)
        else:
            rest_len += int(temp.zfill(8), 2) * pow(128, x - 1)
            offset = x+1
            break
    return rest_len, offset


def gen_conn_msg(dev_id=None, pid=None, apikey=None, auth_info=None, keepalive=300):
    msg_type = b'\x10'              # b1 鉴权连接固定包头 0x10
    # body_len = b''                # b2 剩余字节长度
    proto_desc = b'\x00\x03EDP'     # b3_7 协议描述长度，以及协议描述
    # proto_desc = b'\x00\x03EEP'     # 协议错误
    proto_ver = b'\x01'             # b8 协议版本号1
    keepalive = struct.pack('!H', keepalive)    # 保活时间

    # api-key 方式鉴权
    if dev_id and apikey:
        conn_flag = b'\x40'             # b9 bit7-产品id标识位 bit6鉴权信息标识位 0100 0000

        dev_id_len = struct.pack('!H', len(dev_id))
        dev_id = dev_id.encode('utf-8')
        device = dev_id_len + dev_id

        api_key_len = struct.pack('!H', len(apikey))
        apikey = apikey.encode('utf-8')

        auth = api_key_len + apikey

    # pid和auth_info 方式鉴权
    elif pid and auth_info:
        conn_flag = b'\xc0'             # 1100 0000
        pid_len = struct.pack('!H', len(pid))
        pid = pid.encode('utf-8')
        auth_info_len = struct.pack('!H', len(auth_info))
        auth_info = auth_info.encode('utf-8')
        device = b'\x00\x00'

        auth = pid_len + pid + auth_info_len + auth_info
    else:
        print('CONN_REQ: params error, request params are not given!')
        raise Exception

    rest = proto_desc + proto_ver + conn_flag + keepalive + device + auth
    body_len = bytes([len(rest)])

    conn_msg = msg_type + body_len + rest
    return conn_msg


def gen_push_msg(target_device, msg):
    msg_type = b'\x30'

    if target_device:
        dev_id_len = struct.pack('!H', len(target_device))
        dev_id = target_device.encode('utf-8')
        device = dev_id_len + dev_id
        # print('device', device)
    else:
        device = b''

    if type(msg) == str:
        msg = msg.encode('utf-8')
    elif type(msg) == bytes:
        pass
    else:
        print('PUSH_DATA: message unacceptable!')
        raise Exception

    rest = device + msg
    rest_len = _message_len(len(rest))
    return msg_type + rest_len + rest


def _gen_timestamp():
    t = time.localtime()
    res = [t.tm_year % 100, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec]
    timestamp = bytes(res)
    return timestamp


# 数据类型指示：type=7    //浮点数数据流
def save_type7(float_data, msg_id=None, dev_id=None):
    """
    数据类型指示：type=7    //浮点数数据流
    :param float_data:
    list类型，[(1, 1.1), (2, 2.2)]   (ds_id, float_value)
    :return:
    """
    data_type = b'\x07'
    timestamp = _gen_timestamp()
    data_no = len(float_data)
    data_no = struct.pack('!H', data_no)
    body = data_type + timestamp + data_no
    for ds_id, value in float_data:
        ds_id = struct.pack('!H', ds_id)
        value = struct.pack('f', value)
        body += ds_id + value

    msg_type, rest_head = _gen_save_msg_header(msg_id, dev_id)

    rest = rest_head + body
    rest_len = len(rest)
    rest_len = _message_len(rest_len)

    msg = msg_type + rest_len + rest
    return msg


# 自定义分隔符 type=5
# 消息中最前面两字节为用户自定义的域中分隔符和域间分隔符，这两个分隔符不能相同。比如采用逗号作为域中分隔符，分号作为域间分隔符的格式如下：
# ,;feild0;feild1;…;feildn
# 其中，每个field格式支持3种：
# field格式1： 3个子字段，分别是数据流ID,时间戳，数据值。通用格式：
# Datastream_id,datetime,value
# field格式2： 2个子字段，分别是数据流ID和数据值，省略时间戳。通用格式：
# Datastream_id,value
# field格式3： 1个子字段，省略了数据ID和时间戳，只传输数据值，平台将用该域(feild)所在的位置号（从0开始）作为数据流ID。通用格式：
# value
#
# 示例：
# (1),;temperature,2015-03-22 22:31:12,22.5;102;pm2.5,89;10
# (2)#@temperature#2015-03-22 22:31:12#22.5@102@pm2.5#89@10
def save_type5(data, msg_id, dev_id=None):
    data_type = b'\x05'
    data_len = struct.pack('!H', len(data))
    data = data.encode('utf-8')
    body = data_type + data_len + data

    msg_type, rest_head = _gen_save_msg_header(msg_id, dev_id)
    rest = rest_head + body
    rest_len = _message_len(len(rest))

    msg = msg_type + rest_len + rest
    return msg


# type=6 自定义分隔符，带时间戳
def save_type6(data, msg_id, dev_id=None):
    data_type = b'\x06'

    time_stamp = _gen_timestamp()

    data_len = struct.pack('!H', len(data))
    data = data.encode('utf-8')
    body = data_type + time_stamp + data_len + data

    msg_type, rest_head = _gen_save_msg_header(msg_id, dev_id)
    rest = rest_head + body
    rest_len = _message_len(len(rest))

    msg = msg_type + rest_len + rest
    return msg


# 数据点类型指示：type=4    // JSON格式3字符串
# 通用格式：
# {
# “datastream_id1”:{“datetime1”:”value1”},
# “datastream_id2”: {“datetime2”:”value2”},
# …
# }
#
# 示例：
# {“temperature”:{“2015-03-22 22:31:12”:22.5}}
def save_type4(data, msg_id, dev_id=None):
    data_type = b'\x04'
    data_len = struct.pack('!H', len(data))
    data = data.encode('utf-8')
    body = data_type + data_len + data

    msg_type, rest_head = _gen_save_msg_header(msg_id, dev_id)
    rest = rest_head + body
    rest_len = _message_len(len(rest))

    msg = msg_type + rest_len + rest
    return msg


# 数据点类型指示：type=3    // JSON格式2字符串
# 通用格式：
# {
# “datastream_id1”:”value1”,
# “datastream_id2”:”value2”,
# …
# }
#
# 示例：
# {“temperature”:22.5,”humidity”:”95.2%”}
def save_type3(data, msg_id, dev_id=None):
    data_type = b'\x03'
    data_len = struct.pack('!H', len(data))
    data = data.encode('utf-8')
    body = data_type + data_len + data

    msg_type, rest_head = _gen_save_msg_header(msg_id, dev_id)
    rest = rest_head + body
    rest_len = _message_len(len(rest))

    msg = msg_type + rest_len + rest
    return msg


# 数据点类型指示：type=2    //二进制数据
# {
# ”ds_id”:”image”, //创建数据流时定义的ID，（必填）
# “at”:”2014-10-25 12:23:23”, //时间，（可选）
# ”desc”:字符串或json对象//对该数据的描述（可选）
# }
def save_type2(data, msg_id, ds_id, desc=None, dev_id=None):
    data_type = b'\x02'
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    ds_desc = {'ds_id': ds_id, 'at': t}
    if desc:
        ds_desc['desc'] = desc
    ds_desc = json.dumps(ds_desc).encode('utf-8')
    ds_desc_len = struct.pack('!H', len(ds_desc))
    body = data_type + ds_desc_len + ds_desc

    data_len = struct.pack('!I', len(data))
    body += data_len + data

    msg_type, rest_head = _gen_save_msg_header(msg_id, dev_id)
    rest = rest_head + body
    rest_len = _message_len(len(rest))

    msg = msg_type + rest_len + rest
    return msg


# type1
# {
#  “datastreams
# ”:[// 可以同时传递多个数据流
#        {
# “id”:”temperature”,
# “datapoints”:[
# {
# ”at”:”2013-04-22 22:22:22”,//可选
# ”value”: 36.5//用户自定义
# }
# ]
# },
# {
# “id”:”location”
# “datapoints”:[…]
# }, { … }
# ]
# }
def save_type1(data, msg_id, dev_id=None):
    data_type = b'\x01'
    if type(data) == json:
        data = json.dumps(data)
    data = data.encode('utf-8')
    data_len = struct.pack('!H', len(data))

    body = data_type + data_len + data

    msg_type, rest_head = _gen_save_msg_header(msg_id, dev_id)
    rest = rest_head + body
    rest_len = _message_len(len(rest))

    msg = msg_type + rest_len + rest
    return msg


# 命令解析
def recv_data_parser(recv_data):
    # TODO
    if not recv_data:
        sys.exit()
    elif recv_data[0] == 0x90:
        # 存储确认消息
        msg_id = struct.unpack('!H', recv_data[3:5])[0]
        if recv_data[-1] == 0:
            res = True
        else:
            res = False
        return msg_id, res

    elif recv_data[0] == 0x20:
        # 连接确认消息
        pass
    elif recv_data[0] == 0xA0:
        # 命令消息
        cmd_id, cmd_body = recv_cmd_parser(recv_data)
        return cmd_id, cmd_body
    elif recv_data[0] == 0xD0:
        # 心跳响应
        pass

    elif recv_data[0] == 0x40:
        return False, False


def recv_cmd_parser(cmd_data):
    body_len, length_len = calc_body_len(cmd_data)
    mark = length_len + 1
    cmdid_len = cmd_data[mark:mark+2]
    mark += 2
    cmdid_len = struct.unpack('!H', cmdid_len)[0]
    cmd_id = cmd_data[mark:mark+cmdid_len]
    mark += cmdid_len
    cmdbody_len = cmd_data[mark:mark+4]
    mark += 4
    cmd_body = cmd_data[mark:]
    return cmd_id, cmd_body


def cmd_reply(cmd_id, cmd_resp):
    msg_type = b'\xB0'
    cmd_len = struct.pack('!H', len(cmd_id))
    cmd = cmd_len + cmd_id
    resp_len = struct.pack('!I', len(cmd_resp))
    resp = resp_len + cmd_resp
    rest = cmd + resp
    rest_len = _message_len(len(rest))

    msg = msg_type + rest_len + rest
    return msg


def _gen_save_msg_header(msg_id, dev_id=None):
    msg_type = b'\x80'          # Sava_data 固定包头 0X80

    if dev_id:
        msg_flag = bytes([int('11000000', 2)])
        dev_id_len = struct.pack('!H', len(dev_id))
        dev_id = dev_id.encode('utf-8')
        device = dev_id_len + dev_id
    else:
        msg_flag = bytes([int('01000000', 2)])
        device = b''

    msg_id = struct.pack('!H', msg_id)
    rest_head = msg_flag + device + msg_id
    return msg_type, rest_head


def send_api_cmd(dev_id, command, api_key):
    url = 'http://api.heclouds.com/cmds'
    params = {'device_id': dev_id}
    headers = {'api-key': api_key}
    data = command
    r = requests.post(url, params=params, headers=headers, data=data)
    print(r.text)


def check_cmd_resp(cmd_id, api_key):
    url = 'http://api.heclouds.com/cmds/%s/resp' % cmd_id.decode()
    headers = {'api-key': api_key}
    r = requests.get(url, headers=headers)
    print('API查询命令响应结果:', r.text)


if __name__ == '__main__':
    # 以下设备和产品信息，请自行补全
    api_key = 'xxxx'            # 设备API_KEY
    product_id = 'xxxx'         # 产品ID
    device_id = 'xxxx'          # 设备ID
    auth_info = 'xxxx'          # 鉴权信息

    host = 'jjfaedp.hedevice.com'
    port = 876

    # 生成连接报文
    # conn_msg = gen_conn_msg(device_id, apikey=api_key)
    conn_msg = gen_conn_msg(pid=product_id, auth_info=auth_info)
    print(conn_msg)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))

    # 发送登录报文，并接收响应
    s.send(conn_msg)
    resp = s.recv(1024)
    print('设备注册结果:', resp)

    # 测试PUSH_DATA
    target_dev = '8164739'
    push_data = gen_push_msg(device_id, '123456789')
    print('PUSH DATA: ', push_data)
    s.send(push_data)
    resp = s.recv(1024)
    print('recv:', resp)

    # type=7 浮点数数据流上报
    float_ds = [(1, 22.2000007), (2, 12.2)]     # 传入数据示例
    f_msg = save_type7(float_ds, 1, device_id)
    print(f_msg)
    s.send(f_msg)
    resp = s.recv(1024)
    print('recv:', resp)
    resp = s.recv(1024)
    print('recv:', resp)

    # type=5 自定义分隔符数据流上报
    data = '#@temperature#2015-03-22 22:31:12#22.5@102@pm2.5#89@10'
    t5_data = save_type5(data, 1)
    print(t5_data)
    s.send(t5_data)
    resp = s.recv(1024)
    print('recv:', resp)

    # type=6 自定义分隔符数据流上报
    data = '#@temperature#2015-03-22 22:31:12#22.5@102@pm2.5#89@10'
    t5_data = save_type6(data, 1)
    print(t5_data)
    s.send(t5_data)
    resp = s.recv(1024)
    print('recv:', resp)

    # type=4
    t = time.strftime("%Y-%m-%d %H:%M:%S:")
    data = {'type4': {t: 22.5}}
    t4_data = save_type4(json.dumps(data), 1)
    s.send(t4_data)
    print('send t4_data:', t4_data)
    resp = s.recv(1024)
    print('recv:', resp)

    # type=3
    data = {'type3': 33}
    t3_data = save_type3(json.dumps(data), 1)
    s.send(t3_data)
    print('send t3_data:', t3_data)
    resp = s.recv(1024)
    print('recv:', resp.hex(), resp[-1])

    # type=2
    # data_desc = {'ds_id': 'type2', 'at':t, 'desc': 'test binary data'}
    data = b'abc'
    # data = {'ds_id': 'type2', 'desc': 'test binary'}
    t2_data = save_type2(data, 1, ds_id='type2')
    s.send(t2_data)
    print('send t2_data:', t2_data)
    resp = s.recv(1024)
    print('recv:', resp.hex(), resp[-1])

    # type=1
    data = {'datastreams':[{
        'id': 'type1', 'datapoints':[{
            'at': t,
            'value': 33
        }]}]}
    t1_data = save_type1(json.dumps(data), 1)

    s.send(t1_data)
    print('t1_data', t1_data)
    resp = s.recv(1024)
    print('recv', resp)

    # Send command to device
    # send_api_cmd(device_id, b'command', api_key)
    # recv_data = s.recv(1024)
    # print(recv_data)
    # res = recv_data_parser(recv_data)
    # if res:
    #     cmd_id, cmd_body = res
    #     print('cmd_id:  ', cmd_id)
    #     print('cmd_body:', cmd_body)
    #     s.send(cmd_reply(cmd_id, 'command response'.encode()))
    #     check_cmd_resp(cmd_id, api_key)
