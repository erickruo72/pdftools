#!/bin/bash

echo "=============================="
echo "🚀 Restarting all services..."
echo "=============================="

# Kill Flask on port 5000
FLASK_PID=$(lsof -t -i:5000)
if [ ! -z "$FLASK_PID" ]; then
    echo "Killing Flask process (PID $FLASK_PID)"
    kill -9 $FLASK_PID
fi

# Kill old RQ workers
RQ_PIDS=$(pgrep -f "rq worker")
if [ ! -z "$RQ_PIDS" ]; then
    echo "Killing RQ workers: $RQ_PIDS"
    kill -9 $RQ_PIDS
fi

# Restart Redis
echo "Restarting Redis..."
sudo service redis-server stop
sudo service redis-server start

# Start RQ worker
echo "Starting RQ worker..."
rq worker default &

# Run Flask in dev mode with auto-reload
echo "Starting Flask with auto-reload..."
export FLASK_ENV=development
export FLASK_DEBUG=1
python -m flask run --reload
