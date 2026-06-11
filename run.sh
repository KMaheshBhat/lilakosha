#!/bin/bash

# LilaKosha-Flow-MK1: Pipeline Execution Wrapper

if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found."
    echo "   Please run: cp example.env .env"
    echo "   And update the paths to match your local mount points."
    exit 1
fi

# Pass the --env-file flag to uv run to resolve $LILAKOSHA_* variables
# Usage: ./run.sh config/stage.yml
uv run --env-file .env main.py "$@"
