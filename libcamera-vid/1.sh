#! /bin/bash
source /etc/profile
while true
do
sudo libcamera-vid -t 0 --inline -o - --width 1280 --height 720 --intra 25 \
 --saturation 1.2 --bitrate 5000000 --profile high | \
ffmpeg -re -stream_loop -1 -i "/home/test/out.aac" -f h264 \
-i - -vcodec copy -acodec copy -f flv \
"rtmp://live-push.bilivideo.com/live-bvc/?streamname=\
live_***************&\
key=************************&schedule=rtmp&pflag=1"
sleep 4
done
