/// Shared Chinese display name mapping for tool names.
///
/// Used by both [ToolStepWidget] (new generation steps) and legacy tool
/// execution rendering in [ChatBubble].
const toolDisplayNames = <String, String>{
  // Family management
  'add_family_member': '添加家庭成员',
  'update_member_info': '更新成员信息',
  'query_family_members': '查询家庭成员',
  'get_member_details': '获取成员详情',
  'delete_family_member': '删除家庭成员',

  // Date tools
  'add_important_date': '添加重要日期',
  'query_upcoming_dates': '查询近期日期',
  'update_important_date': '更新重要日期',
  'delete_important_date': '删除重要日期',
  'convert_lunar_date': '农历公历转换',

  // Tasks
  'create_task': '创建任务',
  'query_tasks': '查询任务',
  'complete_task': '完成任务',
  'update_task': '更新任务',
  'delete_task': '删除任务',
  'set_reminder': '设置提醒',

  // Events & schedule
  'create_event': '创建日程',
  'update_event': '更新日程',
  'cancel_schedule': '取消日程',
  'delete_event': '删除事件',
  'search_events': '查询日程',
  'analyze_event_cascade': '分析日程连锁影响',
  'query_external_calendar': '查询外部日历',

  // Travel
  'create_trip': '创建行程',
  'add_trip_itinerary': '添加行程',
  'query_trips': '查询旅行计划',
  'merge_trips': '合并重复行程',
  'update_trip': '更新行程',
  'cancel_trip': '取消行程',
  'query_trip_bookings': '查询行程预订',

  // Favor
  'record_favor': '记录人情',
  'check_favor_balance': '查询人情账',
  'suggest_favor_return': '人情回报建议',
  'recommend_gift': '礼物推荐',
  'create_gift_task': '创建礼物任务',

  // Memory, search & recall
  'search_memory': '查询记忆',
  'save_memory': '保存记忆',
  'update_memory': '更新记忆',
  'web_search': '联网搜索',
  'view_tool_details': '查看执行详情',
  'recall_tool_result': '召回工具结果',
  'call_mcp_tool': '调用外部工具',
  'list_mcp_tools': '列出外部工具',
  'delegate_to_sub_agent': '委托子代理',

  // Weather
  'get_weather': '查询天气',

  // SDK tools
  'Bash': '执行命令',
  'Read': '读取文件',
  'Write': '写入文件',
  'Edit': '编辑文件',
  'Grep': '搜索内容',
  'Glob': '查找文件',
  'LS': '列出目录',
  'WebSearch': '网络搜索',
  'WebFetch': '获取网页',
  'Task': '子任务',
  'TodoWrite': '任务清单',
  'TodoRead': '查看任务',
  'Skill': '技能调用',
  'TaskUpdate': '更新任务',
};

/// Get the Chinese display name for a tool, falling back to snake_case-to-space conversion.
String getToolDisplayName(String toolName) {
  return toolDisplayNames[toolName] ?? toolName.replaceAll('_', ' ');
}
