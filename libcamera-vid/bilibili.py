# coding: utf-8
import random

from edp_sdk import *
from edp_error_codes import *
from onenet_msg import *

log_msg = []
cmd_uuid = ''


def ts_print(*args, prefix='', end=''):
    t = time.strftime("[%Y-%m-%d %H:%M:%S]:")
    print(t, *args)
    temp = t
    for x in args:
        temp += ' ' + str(x)
    temp += '\n'
    if len(log_msg) > 100:
        log_msg.pop(0)
    log_msg.append(temp)


def api_params_check(api_host='a', dev_id='b', api_key='c', cmd='d', timeout=1):
    if not api_host:
        ts_print('Command Error: API address is required')
        return
    if not dev_id:
        ts_print('Command Error: device_id is required')
        return
    if not api_key:
        ts_print('Command Error: api_key is required')
        return
    if not cmd:
        ts_print('Command Error: command content is required')
        return
    if timeout == '':
        pass
    else:
        try:
            int(timeout)
        except ValueError:
            ts_print('Command Error: timeout should be int')
            return
    return True


def send_api_cmd(api_host, dev_id, command, api_key, timeout=0):
    if not api_params_check(api_host, dev_id, api_key, command, timeout=0):
        return
    global cmd_uuid
    url = api_host + '/cmds'
    params = {'device_id': dev_id}
    if timeout:
        params['timeout'] = timeout
    headers = {'api-key': api_key}
    data = command
    if type(data) == str:
        data = data.encode()
    r = requests.post(url, params=params, headers=headers, data=data)
    resp = json.loads(r.text)
    if resp['errno'] == 0:
        cmd_uuid = resp['data']['cmd_uuid']
    resp = json.dumps(resp, sort_keys=True, indent=4, separators=(',', ':'))
    ts_print('API Response: ' + resp)


def check_cmd_status(api_host, cmd_id, api_key):
    ts_print('cmd_uuid: %s' % cmd_uuid)
    if not api_params_check(api_host, api_key=api_key):
        return
    url = api_host + '/cmds/%s' % cmd_id
    headers = {'api-key': api_key}
    r = requests.get(url, headers=headers)
    resp = json.dumps(json.loads(r.text), sort_keys=True, indent=4, separators=(',', ':'))
    ts_print('Command Status: ' + resp)


def check_cmd_resp(api_host, cmd_id, api_key):
    ts_print('cmd_uuid: %s' % cmd_uuid)
    if not api_params_check(api_host, api_key=api_key):
        return
    url = api_host + '/cmds/%s/resp' % cmd_id
    headers = {'api-key': api_key}
    r = requests.get(url, headers=headers)
    ts_print('Command Response:', r.content)


class EDPDevice:
    def __init__(self, host, port, device_id=None, api_key=None, product_id=None, auth_info=None, conn_type=0,
                 auto_cmd_reply=True, enable_dp=True):
        self.host = host
        self.port = port
        self.device_id = device_id
        self.api_key = api_key
        self.product_id = product_id
        self.auth_info = auth_info
        self.status = False
        self.data = b''
        self.msg_id = random.randint(0, 65535)
        self.cmd_reply = auto_cmd_reply
        self.conn_type = conn_type
        self.enable_dp = enable_dp

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def _get_msg_id(self):
        self.msg_id += 1
        if self.msg_id >= 65536:
            self.msg_id = 0
        return self.msg_id

    def _parse_connect_resp(self):
        if len(self.data) < 4:
            ts_print('连接响应报文长度不足，等待下一个报文！')
            return
        rest_len = self.data[1]
        byte3 = self.data[2]
        res_code = self.data[3]
        self.data = self.data[4:]
        if not res_code:
            ts_print('Connection Result: %s -- %s' % (res_code, CONNECT_RESP[res_code]))
        else:
            ts_print('Device Error: Connection Result: %s -- %s' % (res_code, CONNECT_RESP[res_code]))

        if rest_len == 2:
            self.data = self.data[4:]
        elif rest_len < 2:
            ts_print('Device Error: CONNECT Response Error, connect response length not match (less than 4 bytes)')
            self.data = self.data[2+rest_len:]
        else:
            ac_len = struct.unpack('!H', self.data[4:6])[0]
            if len(self.data) >= 4+2+ac_len:
                ac = self.data[6:6+ac_len]
                self.data = self.data[4+2+ac_len:]
                ts_print('授权码：%s' % ac)
                return True
            else:
                ts_print('连接响应报文中授权码长度不足，等待下一个报文！')
        return

    def _parse_save_resp(self):

        if len(self.data) < 6:
            ts_print('存储确认消息长度不足，等待下一个报文！')
            return
        rest_len = self.data[1]
        if rest_len != 4:
            ts_print('异常报文：存储消息长度值异常！丢弃当前报文：%s' % self.data)
            self.data = b''

        msg_id = struct.unpack('!H', self.data[3:5])[0]
        res_code = self.data[5]
        if res_code in SAVE_RESP.keys():
            # ts_print('存储确认%s 消息ID：%s' % (SAVE_RESP[res_code], msg_id))
            pass
        else:
            ts_print('报文异常，不存在的存储确认响应码：%d' % res_code)
            return
        self.data = self.data[6:]
        return True

    def _parse_cmd_req(self):
        if len(self.data) < 1+1+2+36+4:
            ts_print('命令请求消息长度不足，等待下一个报文！')
            return

        body_len, length_len = calc_body_len(self.data)
        mark = length_len + 1
        cmdid_len = self.data[mark:mark + 2]
        mark += 2
        cmdid_len = struct.unpack('!H', cmdid_len)[0]
        cmd_id = self.data[mark:mark + cmdid_len]
        mark += cmdid_len
        cmdbody_len = self.data[mark:mark + 4]
        cmdbody_len = struct.unpack('!i', cmdbody_len)[0]
        mark += 4
        cmd_body = self.data[mark:mark+cmdbody_len]
        mark += cmdbody_len
        if len(self.data) < mark:
            ts_print('命令请求消息长度不足，等待下一个报文！')
            return
        self.data = self.data[mark:]
        return cmd_id, cmd_body

    def _parse_heartbeat_resp(self):
        if len(self.data) < 2:
            ts_print('心跳响应消息长度不足，等待下一个报文！')
            return
        if self.data[1] == 0:
            self.data = self.data[2:]
            return True
        else:
            ts_print('报文异常，心跳响应长度异常：%s' % self.data)
            self.data = b''

    def _parse_disconnect_msg(self):
        if len(self.data) < 3:
            ts_print('连接关闭消息长度不足，等待下一个报文！')
            return
        else:
            if self.data[1] == 1:
                res_code = self.data[2]
                ts_print('连接关闭，错误码：%s -- %s' % (res_code, DISCONNECT_RESP[res_code]))
                self.status = False
                return False
            else:
                ts_print('关闭连接消息异常，等待下一个报文！')

    def _parse_push_msg(self):
        if len(self.data) <= 4:     # 0x30 + rest_len + device_id_len + device_id
            ts_print('透传消息长度不足，等待下一个报文！')
            return

        rest_len, offset = parse_body_len(self.data)
        mark = offset
        # print(mark, rest_len, len(self.data))
        if len(self.data) < rest_len + mark:
            ts_print('透传消息长度不足，等待下一个报文！')
            return
        else:
            org_dev_len = self.data[mark:mark+2]
            org_dev_len = struct.unpack('!H', org_dev_len)[0]
            mark += 2
            org_dev = self.data[mark:mark+org_dev_len]
            mark += org_dev_len
            msg = self.data[mark:offset+rest_len]
            ts_print('收到来自设备ID %s 的透传消息：%s' % (org_dev.decode(), msg))
            self.data = self.data[offset+rest_len:]
            # print('除掉后', self.data)
            return True

    def _parse_forward_msg(self):
        if len(self.data) < 1+1+1:
            ts_print('存储转发消息长度不足，等待下一个报文！')
            return
        rest_len, offset = parse_body_len(self.data)
        # print(rest_len, offset)
        mark = offset

        if len(self.data) < rest_len + mark:
            ts_print('存储转发消息长度不足，等待下一个报文！')
            return

        # print(mark+1)
        biaozhi = bin(self.data[mark])[2:]
        org_dev = ''
        if len(biaozhi) == 8:
            mark += 1

            org_dev_len = self.data[mark:mark + 2]
            org_dev_len = struct.unpack('!H', org_dev_len)[0]
            mark += 2
            org_dev = self.data[mark:mark + org_dev_len].decode()
            mark += org_dev_len
            # print(org_dev_len, org_dev)
        data_type = self.data[mark]
        # ts_print('DataType: %d' % data_type, self.data[mark+1:])
        msg = self.data[mark+1:offset + rest_len]
        if org_dev:
            ts_print('收到来自设备ID %s 的存储转发消息: %s' % (org_dev, msg))
        if data_type == 7:
            timestamp = msg[:6]
            temp = []
            for x in range(6):
                temp.append(str(timestamp[x]).zfill(2))
            timestamp = '20%s-%s-%s %s:%s:%s' % (temp[0], temp[1], temp[2], temp[3], temp[4], temp[5])
            # ts_print('消息时间：' + timestamp)

            float_count = struct.unpack('!H', msg[6:8])[0]
            # ts_print('数据点个数: %s' % float_count)
            message = ''
            float_data = msg[8:]
            for x in range(len(float_data)//6):
                single_float = float_data[x*6:(x+1)*6]
                ds_id = struct.unpack('!H', single_float[:2])[0]
                ds_value = struct.unpack('f', single_float[2:])[0]
                message += '%s --> %s ' % (ds_id, ds_value)
            message += timestamp
            ts_print(message)

        self.data = self.data[offset + rest_len:]
        return True

    # 命令解析
    def recv_data_parser(self):
        # TODO
        res = False
        if not self.data:
            pass
        elif self.data[0] == 0x90:
            res = self._parse_save_resp()

        elif self.data[0] == 0x20:
            res = self._parse_connect_resp()

        elif self.data[0] == 0xA0:
            # 命令消息
            res = self._parse_cmd_req()
            if res:
                cmd_id, cmd_body = res
                ts_print('Receive Command: %s %s' % (cmd_id, cmd_body))
                cmd_resp = cmd_reply(cmd_id, cmd_body)
                if self.cmd_reply:
                    self.sock.send(cmd_resp)
                    ts_print('Send Command Response: %s' % cmd_body)
                msg=str(cmd_body.decode())
                print(msg)
                onenet_rcv(msg)
                #msglist=msg.split(':')
                #for value in msglist:
                #    print(value)

        elif self.data[0] == 0xD0:
            # 心跳响应
            res = self._parse_heartbeat_resp()

        elif self.data[0] == 0x40:
            # 连接关闭
            res = self._parse_disconnect_msg()
        elif self.data[0] == 0x30:
            res = self._parse_push_msg()
        elif self.data[0] == 0x80:
            # 存储转发消息
            res = self._parse_forward_msg()
        else:
            ts_print('未知消息，丢弃此消息！')

        # print(res)
        if res:
            self.recv_data_parser()

    def run(self):
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(.1)

        if not self.conn_type:
            if self.device_id and self.api_key:
                conn_msg = gen_conn_msg(dev_id=self.device_id, apikey=self.api_key)
            else:
                ts_print('Device Error: device_id and api_key is required')
                return
        else:
            if self.product_id and self.auth_info:
                conn_msg = gen_conn_msg(pid=self.product_id, auth_info=self.auth_info)
            else:
                ts_print('Device Error: product_id and auth_info is required')
                return
        self.status = True
        ts_print('发送连接报文：%s', conn_msg)
        self.sock.send(conn_msg)
        # data = self.sock.recv(1024)
        count = 0
        interval = 150

        while self.status:
            try:
                data = self.sock.recv(1024)
                if not data:
                    ts_print('报文接收异常，设备可能已经断开连接，退出程序！')
                    self.status = False
                # ts_print('recv:', data)
                self.data += data
            except Exception as e:
                if 'timed out' in str(e):
                    count += 1
                    if self.data:
                        ts_print('异常报文：%s' % self.data)
                        self.data = b''

                    action = count % interval
                    if self.enable_dp:
                        if action == 31:
                            push_data = gen_push_msg(self.device_id, str(self.msg_id)*1)
                            ts_print('发送透传消息: %s' % push_data, self.msg_id)
                            self.sock.send(push_data)
                            # self.msg_id += 1

                        elif action == 32:
                            # type=7 浮点数数据流上报
                            f_data = random.randint(-1000, 1000)/10
                            float_ds = [(1, f_data), (2, f_data)]  # 传入数据示例
                            # for x in range(1):
                            #     float_ds.append((x, (x+1)*0.01))
                            # print(float_ds)
                            f_msg = save_type7(float_ds, self._get_msg_id(), self.device_id)
                            # print(f_msg)
                            self.sock.send(f_msg)
                            ts_print('send dp(type 7)：', '1 -->', f_data, '2 -->', f_data)

                        elif action == 33:
                            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                            temperature = random.randint(-10, 40)
                            data = '#@temperature#%s#%s@pm2.5#59' % (current_time, temperature)
                            t5_data = save_type5(data, self._get_msg_id())
                            # ts_print(t5_data)
                            self.sock.send(t5_data)
                            ts_print('send dp(type 5)：', 'temperature -->', temperature, 'pm2.5 -->', 59)

                        elif action == 34:
                            # type=6 自定义分隔符数据流上报
                            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                            temperature = random.randint(-10, 40)
                            data = '#@temperature#%s#%s@pm2.5#69' % (current_time, temperature)
                            t6_data = save_type6(data, self._get_msg_id())
                            # ts_print(t6_data)
                            self.sock.send(t6_data)
                            ts_print('send dp(type 6)：', 'temperature -->', temperature, 'pm2.5 -->', 69)

                        elif action == 35:
                            # type=4
                            t = time.strftime("%Y-%m-%d %H:%M:%S")
                            value = random.randint(0, 100)
                            data = {'type4': {t: value}}
                            t4_data = save_type4(json.dumps(data), self._get_msg_id())
                            self.sock.send(t4_data)
                            # ts_print('send t4_data:', t4_data)
                            ts_print('send dp(type 4)：', 'type4 -->', value, 'time: %s' % t)

                        elif action == 36:
                            # type=3简单
                            value = random.randint(0, 100)
                            data = {'type3': value}
                            t3_data = save_type3(json.dumps(data), self._get_msg_id())
                            self.sock.send(t3_data)
                            # ts_print('send t3_data:', t3_data)
                            ts_print('send dp(type 3)：', 'type3 -->', value)

                        elif action == 37:
                            # type=2
                            # data_desc = {'ds_id': 'type2', 'at':t, 'desc': 'test binary data'}
                            data = []
                            for x in range(random.randint(3, 10)):
                                data.append(random.randint(0, 255))
                            data = bytes(data)
                            # data = {'ds_id': 'type2', 'desc': 'test binary'}
                            t2_data = save_type2(data, self._get_msg_id(), ds_id='type2')
                            self.sock.send(t2_data)
                            # ts_print('send t2_data:', t2_data)
                            ts_print('send dp(type 2)：', 'type2 -->', data.hex())

                        elif action == 38:
                            # type=1
                            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                            value = random.randint(0, 100)
                            data = {'datastreams': [{
                                'id': 'type1', 'datapoints': [{
                                    'at': current_time,
                                    'value': value
                                }]}]}
                            t1_data = save_type1(json.dumps(data), self._get_msg_id())

                            self.sock.send(t1_data)
                            # ts_print('t1_data', t1_data)
                            ts_print('send dp(type 1)：', 'type1 -->', value)

                    else:
                        if action == 30:
                            self.sock.send(HEART_BEAT)
                            # ts_print('send ping request')

                else:
                    ts_print(e)
            else:
                self.recv_data_parser()
        else:
            self.sock.close()
            ts_print('EDP device exit!')


if __name__ == '__main__':
    # 以下设备和产品信息，请自行补全
    api_key = '****'            # 设备API_KEY
    product_id = '****'         # 产品ID
    device_id = '****'          # 设备ID
    auth_info = '****'          # 鉴权信息

    host = 'jjfaedp.hedevice.com'
    port = 876

    device = EDPDevice(host, port, device_id, api_key, product_id, auth_info)
    device.run()
