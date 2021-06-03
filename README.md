# OnenetBilibili
  
**设计目的：**
远程通过中移物联网的应用平台打开家里的树莓派推流直播，
直播地址http://live.bilibili.com/22658118



**操作方法：**

1、编辑1.sh，参考你的bilibili直播码，把streamname和key赋上值

2、把编辑后的1.sh放到/bin目录并给个执行权限。命令sudo cp 1.sh  /bin/1.sh |chmod 777 /bin/1.sh

3、命令行1.sh回车，测试一下推流是否正常然后关闭。下面测试中移物联网的部分。

4、先注册中移物联网，建立EDP协议工程，加个 blue_statu名字的数据流。然后编辑bilibili.py最后几段，把API KEY和产品ID等填上

5、启动OneNet客户端，命令python3 bilibili.py回车。观察输出，如果连接失败一般是产品ID等信息填错。

6、保持bilibili.py运行。在中移物联网平台建立一个应用并做个按钮开关。开关关值0，开值1，开关EDP命令内容blue_statu:{V}。预览应用并点一下开关。



**原理：**
树莓派使用Python连接中移Onenet物联网平台，然后通过Onenet网页应用的按钮下发命令到树莓派，树莓派解析到对应的命令流后启动B站推流脚本。

