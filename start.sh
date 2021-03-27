kill -9 `cat /opt/matchmaking/pid`
echo "" > /opt/matchmaking/pid
nohup python /opt/matchmaking/matchmaking.py &
echo $! > /opt/matchmaking/pid
