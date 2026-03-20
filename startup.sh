#!/bin/bash

echo "Starting DevGuard API..."

uvicorn api.main:app --host 0.0.0.0 --port 8000