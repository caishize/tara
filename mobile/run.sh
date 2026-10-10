#!/bin/bash

# Flutter 移动端开发启动脚本
# 支持热更新: 按 r = Hot Reload, 按 R = Hot Restart, 按 q = 退出

set -e

# 设置 Flutter 路径
export PATH="$HOME/development/flutter/bin:$PATH"

# 切换到 mobile 目录
cd "$(dirname "$0")"

echo "=========================================="
echo "  Family Secretary - Flutter 移动端"
echo "=========================================="
echo ""

# 检查 Flutter 是否可用
if ! command -v flutter &> /dev/null; then
    echo "❌ 错误: 找不到 Flutter"
    echo "请确认 Flutter 安装路径,并修改脚本中的 PATH"
    exit 1
fi

# 显示 Flutter 版本
echo "📱 Flutter 版本:"
flutter --version | head -1
echo ""

# 检查连接的设备
echo "🔍 检查连接的设备..."
flutter devices
echo ""

# 获取依赖 (如果需要)
if [ ! -d ".dart_tool" ] || [ "pubspec.yaml" -nt ".dart_tool/package_config.json" ]; then
    echo "📦 获取依赖..."
    flutter pub get
    echo ""
fi

# 启动应用
echo "🚀 启动应用 (支持热更新)..."
echo ""
echo "=========================================="
echo "  快捷键说明:"
echo "  r = Hot Reload (快速刷新UI)"
echo "  R = Hot Restart (完全重启应用)"
echo "  q = 退出"
echo "  h = 显示更多帮助"
echo "=========================================="
echo ""

# 运行 Flutter (默认 debug 模式)
flutter run "$@"
