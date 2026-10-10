import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/chat_message.dart';
import 'card_quick_actions.dart';
import 'chat_bubble.dart' show buildQuickActionsRow;
import 'expandable_content_section.dart';
import 'message_action_bar.dart';

/// A chat bubble widget that displays task cards
class TaskListBubble extends StatefulWidget {
  final ChatMessage message;
  final void Function(String messageId)? onRegenerate;
  final void Function(String messageId, bool isLike, String? reason)? onFeedback;
  final void Function(QuickAction action)? onQuickAction;

  const TaskListBubble({
    super.key,
    required this.message,
    this.onRegenerate,
    this.onFeedback,
    this.onQuickAction,
  });

  @override
  State<TaskListBubble> createState() => _TaskListBubbleState();
}

class _TaskListBubbleState extends State<TaskListBubble> {
  ChatMessage get message => widget.message;

  static const _headerGradient = LinearGradient(
    colors: [Color(0xFF7B1FA2), Color(0xFFAB47BC)],
  );

  @override
  Widget build(BuildContext context) {
    final data = message.data ?? {};
    final tasks = _extractTasks(data);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAvatar(),
          const SizedBox(width: 8),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeaderCard(context),
                const SizedBox(height: 8),
                if (message.content.isNotEmpty && message.content.length > 20)
                  ExpandableContentSection(content: message.content),
                ...tasks.take(5).map((task) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: _buildTaskItem(context, task),
                )),
                if (tasks.length > 5)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      '还有 ${tasks.length - 5} 个任务...',
                      style: AppTextStyles.caption.copyWith(
                        color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                      ),
                    ),
                  ),
                _buildViewAllButton(context),
                ..._buildQuickActionsSection(),
                const SizedBox(height: 4),
                _buildMessageActionBar(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _extractTasks(Map<String, dynamic> data) {
    if (data['tasks'] is List) {
      return (data['tasks'] as List)
          .whereType<Map<String, dynamic>>()
          .toList();
    }
    // Single task shape
    if (data['title'] != null || data['task_title'] != null) {
      return [data];
    }
    return [];
  }

  List<Widget> _buildQuickActionsSection() {
    final actions = resolveQuickActions(message, 'task_card');
    if (actions.isEmpty) return const [];
    return [
      Padding(
        padding: const EdgeInsets.only(top: 8),
        child: buildQuickActionsRow(actions, onTap: widget.onQuickAction),
      ),
    ];
  }

  Widget _buildHeaderCard(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: _headerGradient,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.checklist, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              '任务列表',
              style: AppTextStyles.subtitle2.copyWith(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTaskItem(BuildContext context, Map<String, dynamic> task) {
    final title = (task['title'] ?? task['task_title'] ?? '任务') as String;
    final status = task['status'] as String? ?? 'pending';
    final priority = task['priority'] as String? ?? 'medium';
    final dueDate = task['due_date'] as String?;
    final description = task['description'] as String?;

    final priorityColor = _getPriorityColor(context, priority);
    final isCompleted = status == 'completed' || status == 'done';

    return GestureDetector(
      onTap: () => _showTaskDetail(context, task),
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
        ),
        decoration: BoxDecoration(
          color: Theme.of(context).extension<AppColorsExtension>()!.cardBackground,
          borderRadius: BorderRadius.circular(10),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.04 * Theme.of(context).extension<AppColorsExtension>()!.shadowOpacity),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              // Priority dot
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: priorityColor,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 10),
              // Status icon
              Icon(
                isCompleted ? Icons.check_circle : Icons.radio_button_unchecked,
                size: 18,
                color: isCompleted ? AppColors.success : Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
              ),
              const SizedBox(width: 8),
              // Title & due date
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: AppTextStyles.bodyText2.copyWith(
                        fontWeight: FontWeight.w500,
                        decoration: isCompleted ? TextDecoration.lineThrough : null,
                        color: isCompleted ? Theme.of(context).extension<AppColorsExtension>()!.textTertiary : Theme.of(context).colorScheme.onSurface,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (dueDate != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        _formatDueDate(dueDate),
                        style: AppTextStyles.overline.copyWith(
                          color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                        ),
                      ),
                    ],
                    if (description != null && description.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        description,
                        style: AppTextStyles.caption.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
              Icon(Icons.chevron_right, size: 18, color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary),
            ],
          ),
        ),
      ),
    );
  }

  void _showTaskDetail(BuildContext context, Map<String, dynamic> task) {
    final title = (task['title'] ?? task['task_title'] ?? '任务') as String;
    final status = task['status'] as String? ?? 'pending';
    final priority = task['priority'] as String? ?? 'medium';
    final dueDate = task['due_date'] as String?;
    final description = task['description'] as String?;
    final notes = task['notes'] as String?;
    final isCompleted = status == 'completed' || status == 'done';

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.of(context).size.height * 0.6,
        ),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Handle
            Center(
              child: Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            Flexible(
              child: ListView(
                shrinkWrap: true,
                padding: const EdgeInsets.symmetric(horizontal: 20),
                children: [
                  // Header
                  Row(
                    children: [
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: const Color(0xFF7B1FA2).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        alignment: Alignment.center,
                        child: Icon(
                          isCompleted ? Icons.check_circle : Icons.checklist,
                          color: const Color(0xFF7B1FA2),
                          size: 24,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              title,
                              style: AppTextStyles.subtitle1.copyWith(
                                fontWeight: FontWeight.bold,
                                decoration: isCompleted ? TextDecoration.lineThrough : null,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: _getPriorityColor(context, priority).withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(
                                    _getPriorityLabel(priority),
                                    style: AppTextStyles.overline.copyWith(
                                      color: _getPriorityColor(context, priority),
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 6),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: isCompleted
                                        ? AppColors.success.withValues(alpha: 0.1)
                                        : AppColors.warning.withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(
                                    isCompleted ? '已完成' : '进行中',
                                    style: AppTextStyles.overline.copyWith(
                                      color: isCompleted ? AppColors.success : AppColors.warning,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  // Due date
                  if (dueDate != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        children: [
                          Icon(Icons.calendar_today, size: 16, color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary),
                          const SizedBox(width: 8),
                          Text(
                            '截止: ${_formatDueDate(dueDate)}',
                            style: AppTextStyles.bodyText2.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                  // Description
                  if (description != null && description.isNotEmpty) ...[
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: Theme.of(context).extension<AppColorsExtension>()!.chipBackground,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        description,
                        style: AppTextStyles.bodyText2.copyWith(height: 1.5),
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                  // Notes
                  if (notes != null && notes.isNotEmpty) ...[
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: const Color(0xFF7B1FA2).withValues(alpha: 0.06),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(Icons.notes, size: 16, color: const Color(0xFF7B1FA2)),
                              const SizedBox(width: 6),
                              Text(
                                '备注',
                                style: AppTextStyles.caption.copyWith(
                                  fontWeight: FontWeight.w600,
                                  color: const Color(0xFF7B1FA2),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            notes,
                            style: AppTextStyles.bodyText2.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                              height: 1.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _getPriorityLabel(String priority) {
    switch (priority.toLowerCase()) {
      case 'high':
      case 'urgent':
        return '紧急';
      case 'medium':
        return '中等';
      case 'low':
        return '低';
      default:
        return priority;
    }
  }

  Color _getPriorityColor(BuildContext context, String priority) {
    switch (priority.toLowerCase()) {
      case 'high':
      case 'urgent':
        return AppColors.error;
      case 'medium':
        return AppColors.warning;
      case 'low':
        return AppColors.success;
      default:
        return Theme.of(context).extension<AppColorsExtension>()!.textTertiary;
    }
  }

  String _formatDueDate(String dateStr) {
    try {
      final dt = DateTime.parse(dateStr).toLocal();
      final now = DateTime.now();
      final diff = dt.difference(now).inDays;
      if (diff == 0) return '今天到期';
      if (diff == 1) return '明天到期';
      if (diff < 0) return '已过期 ${-diff} 天';
      return '${dt.month}/${dt.day} 到期';
    } catch (_) {
      return dateStr;
    }
  }

  Widget _buildViewAllButton(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      child: OutlinedButton.icon(
        onPressed: () {
          // Send a quick action to ask assistant for all tasks
          final action = QuickAction(
            label: '查看全部任务',
            action: '帮我查看所有待办任务',
            type: 'message',
          );
          widget.onQuickAction?.call(action);
        },
        icon: const Icon(Icons.list_alt, size: 16),
        label: const Text('查看全部'),
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFF7B1FA2),
          side: BorderSide(color: const Color(0xFF7B1FA2).withValues(alpha: 0.3)),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        ),
      ),
    );
  }

  Widget _buildAvatar() {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(10),
      ),
      child: const Icon(Icons.auto_awesome, color: Colors.white, size: 18),
    );
  }

  Widget _buildMessageActionBar() {
    return MessageActionBar(
      createdAt: message.createdAt,
      config: MessageActionBarConfig(
        showCopy: true,
        showRegenerate: true,
        showFeedback: true,
        onCopy: () {
          HapticFeedback.lightImpact();
          Clipboard.setData(ClipboardData(text: message.content));
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: const Text('已复制到剪贴板'),
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              duration: const Duration(seconds: 2),
              margin: const EdgeInsets.all(16),
            ),
          );
        },
        onRegenerate: widget.onRegenerate != null
            ? () => widget.onRegenerate!.call(message.id)
            : null,
        onFeedback: (isLike, reason) =>
            widget.onFeedback?.call(message.id, isLike, reason),
      ),
    );
  }
}
