sudo raspivid -o - -t 0 -w 1280 -h 720 -fps 25 -b 10000000 | \
ffmpeg -f h264 -i - -vcodec copy -acodec aac -b:a 192k -f flv \
"rtmp://live-push.bilivideo.com/live-bvc/?streamname=***&key=***&schedule=rtmp&pflag=1"