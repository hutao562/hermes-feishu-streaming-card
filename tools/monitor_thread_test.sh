#!/bin/bash
# 实时监控 sidecar 事件接收和 thread 信息

echo "=== 实时监控 Hermes 事件 ==="
echo "日志位置: ~/.hermes/logs/gateway.log"
echo ""
echo "监控 thread 信息（过滤 Topic debug）:"
echo "tail -f ~/.hermes/logs/gateway.log | grep 'Topic debug'"
echo ""
echo "监控 sidecar 事件:"
echo "curl -s http://127.0.0.1:8765/health | python3 -m json.tool | grep -E 'events_received|active_sessions'"
echo ""
echo "=== 测试步骤 ==="
echo "1. 在飞书私聊中回复一条消息创建话题"
echo "2. 在话题内发送消息给 Hermes"
echo "3. 观察日志中是否出现 thread_id"
echo ""
echo "按 Ctrl+C 停止监控"
echo ""

tail -f ~/.hermes/logs/gateway.log | grep --line-buffered "Topic debug\|events_received"
