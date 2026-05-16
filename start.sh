#!/bin/bash
exec /opt/python/3.11.9/bin/python -m uvicorn gesturesense:app --host 0.0.0.0 --port $PORT
