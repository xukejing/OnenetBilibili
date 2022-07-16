import os
def onenet_rcv(msg):
    msglist=msg.split(':')
    #for value in msglist:
    #    print(value)
    if msglist[0] == 'blue_statu':
        if msglist[1]=='1':
            f=os.popen("1.sh")
        if msglist[1]=='0':
            f=os.popen("pkill 1.sh")
            f=os.popen("pkill ffmpeg")
