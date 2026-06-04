#!/usr/bin/env bash
# scripts/run_dev.sh — Linux/macOS 启动脚本
# 用法：bash scripts/run_dev.sh
set -e
cd "$(dirname "$0")/.."
exec python -m src.main
