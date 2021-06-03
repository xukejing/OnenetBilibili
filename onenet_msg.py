import os
def onenet_rcv(msg):
    msglist=msg.split(':')
    #for value in msglist:
    #    print(value)
    if msglist[0] == 'blue_statu':
        if msglist[1]=='1':
            print(os.system("nohup 1.sh > /home/pi/bilibili.log 2>&1 &"))
