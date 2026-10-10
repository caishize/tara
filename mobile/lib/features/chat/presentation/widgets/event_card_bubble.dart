import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/chat_message.dart';
import 'card_quick_actions.dart';
import 'chat_bubble.dart' show buildQuickActionsRow;
import 'expandable_content_section.dart';
import 'message_action_bar.dart';

/// A chat bubble widget that displays event cards
class EventCardBubble extends StatefulWidget {
  final ChatMessage message;
  final void Function(String messageId)? onRegenerate;
  final void Function(String messageId, bool isLike, String? reason)? onFeedback;
  final void Function(QuickAction action)? onQuickAction;

  const EventCardBubble({
    super.key,
    required this.message,
    this.onRegenerate,
    this.onFeedback,
    this.onQuickAction,
  });

  @override
  State<EventCardBubble> createState() => _EventCardBubbleState();
}

class _EventCardBubbleState extends State<EventCardBubble> {
  ChatMessage get message => widget.message;

  @override
  Widget build(BuildContext context) {
    final data = message.data ?? {};
    final events = _extractEvents(data);

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
                ...events.take(3).map((event) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _buildEventItem(context, event),
                )),
                _buildViewCalendarButton(context),
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

  List<Map<String, dynamic>> _extractEvents(Map<String, dynamic> data) {
    if (data['events'] is List) {
      return (data['events'] as List)
          .whereType<Map<String, dynamic>>()
          .toList();
    }
    // Fallback: older responses use 'schedule' key with task-like fields
    if (data['schedule'] is List) {
      return (data['schedule'] as List)
          .whereType<Map<String, dynamic>>()
          .map((item) {
            return {
              ...item,
              if (item['start_time'] == null && item['due_date'] != null)
                'start_time': item['due_date'],
            };
          })
          .toList();
    }
    // Single event shape: wrap it
    if (data['title'] != null || data['event_title'] != null) {
      return [data];
    }
    return [];
  }

  List<Widget> _buildQuickActionsSection() {
    final actions = resolveQuickActions(message, 'event_card');
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
        gradient: const LinearGradient(
          colors: [Color(0xFF43A047), Color(0xFF66BB6A)],
        ),
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
            child: const Icon(Icons.event, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              '日程安排',
              style: AppTextStyles.subtitle2.copyWith(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEventItem(BuildContext context, Map<String, dynamic> event) {
    final title = (event['title'] ?? event['event_title'] ?? '日程') as String;
    final startTime = event['start_time'] as String?;
    final endTime = event['end_time'] as String?;
    final location = event['location'] as String?;
    final eventType = event['event_type'] as String?;

    String timeRange = '';
    if (startTime != null) {
      timeRange = _formatTimeStr(startTime);
      if (endTime != null) {
        timeRange += ' - ${_formatTimeStr(endTime)}';
      }
    }

    return GestureDetector(
      onTap: () => _showEventDetail(context, event),
      child: Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      decoration: BoxDecoration(
        color: Theme.of(context).extension<AppColorsExtension>()!.cardBackground,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05 * Theme.of(context).extension<AppColorsExtension>()!.shadowOpacity),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Container(
              width: 4,
              height: 48,
              decoration: BoxDecoration(
                color: const Color(0xFF43A047),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          title,
                          style: AppTextStyles.subtitle2.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (eventType != null)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFF43A047).withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            eventType,
                            style: AppTextStyles.overline.copyWith(
                              color: const Color(0xFF43A047),
                              fontSize: 10,
                            ),
                          ),
                        ),
                    ],
                  ),
                  if (timeRange.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(Icons.access_time, size: 12, color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary),
                        const SizedBox(width: 4),
                        Text(
                          timeRange,
                          style: AppTextStyles.caption.copyWith(
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ],
                  if (location != null && location.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Icon(Icons.location_on, size: 12, color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            location,
                            style: AppTextStyles.caption.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    ),
    );
  }

  void _showEventDetail(BuildContext context, Map<String, dynamic> event) {
    final title = (event['title'] ?? event['event_title'] ?? '日程') as String;
    final startTime = event['start_time'] as String?;
    final endTime = event['end_time'] as String?;
    final location = event['location'] as String?;
    final eventType = event['event_type'] as String?;
    final description = event['description'] as String?;
    final notes = event['notes'] as String?;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.5,
        maxChildSize: 0.85,
        minChildSize: 0.3,
        builder: (_, __) => Container(
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          ),
          child: Column(
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
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  children: [
                    // Header
                    Row(
                      children: [
                        Container(
                          width: 48,
                          height: 48,
                          decoration: BoxDecoration(
                            color: const Color(0xFF43A047).withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          alignment: Alignment.center,
                          child: const Icon(
                            Icons.event,
                            color: Color(0xFF43A047),
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
                                ),
                              ),
                              if (eventType != null) ...[
                                const SizedBox(height: 4),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 3,
                                  ),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF43A047).withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(
                                    eventType,
                                    style: AppTextStyles.overline.copyWith(
                                      color: const Color(0xFF43A047),
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    // Time
                    if (startTime != null)
                      _buildDetailRow(
                        Icons.access_time,
                        '时间',
                        _formatDetailTimeRange(startTime, endTime),
                      ),
                    // Location
                    if (location != null && location.isNotEmpty)
                      _buildDetailRow(
                        Icons.location_on_outlined,
                        '地点',
                        location,
                      ),
                    // Description
                    if (description != null && description.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      Container(
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
                    ],
                    // Notes
                    if (notes != null && notes.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.06),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(Icons.notes, size: 16, color: Theme.of(context).colorScheme.primary),
                                const SizedBox(width: 6),
                                Text(
                                  '备注',
                                  style: AppTextStyles.caption.copyWith(
                                    fontWeight: FontWeight.w600,
                                    color: Theme.of(context).colorScheme.primary,
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
                    const SizedBox(height: 32),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDetailRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 18, color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary),
          const SizedBox(width: 10),
          SizedBox(
            width: 48,
            child: Text(
              label,
              style: AppTextStyles.bodyText2.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTextStyles.bodyText2,
            ),
          ),
        ],
      ),
    );
  }

  String _formatDetailTimeRange(String startTime, String? endTime) {
    try {
      final start = DateTime.parse(startTime).toLocal();
      final dateFormat = '${start.month}/${start.day} ${start.hour.toString().padLeft(2, '0')}:${start.minute.toString().padLeft(2, '0')}';
      if (endTime != null) {
        final end = DateTime.parse(endTime).toLocal();
        final endFormat = '${end.month}/${end.day} ${end.hour.toString().padLeft(2, '0')}:${end.minute.toString().padLeft(2, '0')}';
        return '$dateFormat - $endFormat';
      }
      return dateFormat;
    } catch (_) {
      return startTime;
    }
  }

  Widget _buildViewCalendarButton(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      child: OutlinedButton.icon(
        onPressed: () => context.push(Routes.kanban),
        icon: const Icon(Icons.calendar_today, size: 16),
        label: const Text('查看日历'),
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFF43A047),
          side: BorderSide(color: const Color(0xFF43A047).withValues(alpha: 0.3)),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        ),
      ),
    );
  }

  String _formatTimeStr(String isoTime) {
    try {
      final dt = DateTime.parse(isoTime).toLocal();
      return '${dt.month}/${dt.day} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return isoTime;
    }
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
