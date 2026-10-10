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

/// A chat bubble widget that displays upcoming important dates
class UpcomingDatesBubble extends StatefulWidget {
  final ChatMessage message;
  final void Function(String messageId)? onRegenerate;
  final void Function(String messageId, bool isLike, String? reason)? onFeedback;
  final void Function(QuickAction action)? onQuickAction;

  const UpcomingDatesBubble({
    super.key,
    required this.message,
    this.onRegenerate,
    this.onFeedback,
    this.onQuickAction,
  });

  @override
  State<UpcomingDatesBubble> createState() => _UpcomingDatesBubbleState();
}

class _UpcomingDatesBubbleState extends State<UpcomingDatesBubble> {
  ChatMessage get message => widget.message;

  static const _headerGradient = LinearGradient(
    colors: [Color(0xFFC2185B), Color(0xFFE91E63)],
  );

  @override
  Widget build(BuildContext context) {
    final data = message.data ?? {};
    final dates = _extractDates(data);

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
                ...dates.take(5).map((date) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: _buildDateItem(context, date),
                )),
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

  List<Map<String, dynamic>> _extractDates(Map<String, dynamic> data) {
    if (data['dates'] is List) {
      return (data['dates'] as List)
          .whereType<Map<String, dynamic>>()
          .toList();
    }
    if (data['upcoming_dates'] is List) {
      return (data['upcoming_dates'] as List)
          .whereType<Map<String, dynamic>>()
          .toList();
    }
    return [];
  }

  List<Widget> _buildQuickActionsSection() {
    final actions = resolveQuickActions(message, 'upcoming_dates');
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
            child: const Icon(Icons.date_range, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              '重要日期',
              style: AppTextStyles.subtitle2.copyWith(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDateItem(BuildContext context, Map<String, dynamic> date) {
    final title = (date['title'] ?? date['name'] ?? '日期') as String;
    final dateStr = date['date'] as String?;
    final calendarType = date['calendar_type'] as String? ?? 'solar';
    final isLunar = calendarType == 'lunar';
    final daysUntil = _computeDaysUntil(dateStr);

    return Container(
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
            // Calendar type badge
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
              decoration: BoxDecoration(
                color: isLunar ? Theme.of(context).extension<AppColorsExtension>()!.badgePink : Theme.of(context).extension<AppColorsExtension>()!.badgeBlue,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                isLunar ? '农' : '公',
                style: AppTextStyles.overline.copyWith(
                  color: isLunar ? const Color(0xFFC2185B) : Colors.blue.shade700,
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: AppTextStyles.bodyText2.copyWith(
                      fontWeight: FontWeight.w500,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (dateStr != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      _formatDateStr(dateStr),
                      style: AppTextStyles.overline.copyWith(
                        color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            // Countdown
            if (daysUntil != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: daysUntil <= 7
                      ? AppColors.error.withValues(alpha: 0.1)
                      : Theme.of(context).extension<AppColorsExtension>()!.chipBackground,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  daysUntil == 0
                      ? '今天'
                      : daysUntil < 0
                          ? '已过'
                          : '还有${daysUntil}天',
                  style: AppTextStyles.caption.copyWith(
                    color: daysUntil <= 7 ? AppColors.error : Theme.of(context).colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  int? _computeDaysUntil(String? dateStr) {
    if (dateStr == null) return null;
    try {
      final dt = DateTime.parse(dateStr);
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final target = DateTime(dt.year, dt.month, dt.day);
      return target.difference(today).inDays;
    } catch (_) {
      return null;
    }
  }

  String _formatDateStr(String dateStr) {
    try {
      final dt = DateTime.parse(dateStr);
      return '${dt.year}/${dt.month}/${dt.day}';
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
        onPressed: () => context.push(Routes.dates),
        icon: const Icon(Icons.calendar_month, size: 16),
        label: const Text('查看全部'),
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFFC2185B),
          side: BorderSide(color: const Color(0xFFC2185B).withValues(alpha: 0.3)),
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
