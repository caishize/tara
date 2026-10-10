import '../../domain/entities/chat_message.dart';

/// Default quick actions per card intent type.
/// Mirrors backend card_config.py — used as fallback when the server
/// does not attach quick_actions to a card response.
const Map<String, List<QuickAction>> defaultCardQuickActions = {
  'event_card': [
    QuickAction(
      label: '调整日期',
      action: '帮我调整这个日程的时间',
      type: 'message',
      icon: 'calendar_month',
    ),
    QuickAction(
      label: '取消日程',
      action: '帮我取消这个日程',
      type: 'message',
      icon: 'cancel',
      variant: 'destructive',
    ),
  ],
  'task_card': [
    QuickAction(
      label: '新建任务',
      action: '帮我新建一个任务',
      type: 'message',
      icon: 'add_task',
    ),
    QuickAction(
      label: '完成任务',
      action: '帮我标记任务为已完成',
      type: 'message',
      icon: 'check_circle',
    ),
  ],
  'member_profile': [
    QuickAction(
      label: '更新信息',
      action: '帮我更新这个家人的信息',
      type: 'message',
      icon: 'edit',
    ),
    QuickAction(
      label: '查看偏好',
      action: '查看这个家人的偏好',
      type: 'message',
      icon: 'favorite',
    ),
  ],
  'recommend_gift': [
    QuickAction(
      label: '查看详情',
      action: '帮我看看这个礼物的详情',
      type: 'message',
      icon: 'card_giftcard',
    ),
    QuickAction(
      label: '换个推荐',
      action: '帮我换一些礼物推荐',
      type: 'message',
      icon: 'refresh',
    ),
  ],
  'upcoming_dates': [
    QuickAction(
      label: '添加日期',
      action: '帮我添加一个重要日期',
      type: 'message',
      icon: 'event',
    ),
    QuickAction(
      label: '查看详情',
      action: '帮我查看近期日期详情',
      type: 'message',
      icon: 'info',
    ),
  ],
  'favor_balance': [
    QuickAction(
      label: '记录人情',
      action: '帮我记录一笔人情',
      type: 'message',
      icon: 'handshake',
    ),
    QuickAction(
      label: '回报建议',
      action: '/relationships/favors',
      type: 'navigate',
      icon: 'lightbulb',
    ),
  ],
};

/// Resolve quick actions for a card bubble:
/// use message.quickActions if present, otherwise fall back to defaults.
List<QuickAction> resolveQuickActions(
  ChatMessage message,
  String intentKey,
) {
  if (message.quickActions != null && message.quickActions!.isNotEmpty) {
    return message.quickActions!;
  }
  return defaultCardQuickActions[intentKey] ?? const [];
}
