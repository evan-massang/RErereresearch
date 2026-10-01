#!/usr/bin/env bash
# start | stop | status for the live recorder (uses a PID file, never pattern-kills).
cd "$(dirname "$0")/.."
PIDF=data/recorder.pid
case "${1:-status}" in
  start)
    if [[ -f $PIDF ]] && kill -0 "$(cat $PIDF)" 2>/dev/null; then echo "already running ($(cat $PIDF))"; exit 0; fi
    mkdir -p data/logs
    setsid nohup python3 -m pipeline.recorder --hours "${2:-9}" >> data/logs/recorder.log 2>&1 < /dev/null &
    echo $! > $PIDF; echo "started $(cat $PIDF)";;
  stop)
    [[ -f $PIDF ]] && kill "$(cat $PIDF)" 2>/dev/null; rm -f $PIDF; echo stopped;;
  status)
    if [[ -f $PIDF ]] && kill -0 "$(cat $PIDF)" 2>/dev/null; then echo "running ($(cat $PIDF))"; else echo "not running"; fi
    cat data/recorder_status.json 2>/dev/null; echo;;
esac
