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

/// A chat bubble widget that displays favor balance / social ledger cards
class FavorBalanceBubble extends StatefulWidget {
  final ChatMessage message;
  final void Function(String messageId)? onRegenerate;
  final void Function(String messageId, bool isLike, String? reason)? onFeedback;
  final void Function(QuickAction action)? onQuickAction;

  const FavorBalanceBubble({
    super.key,
    required this.message,
    this.onRegenerate,
    this.onFeedback,
    this.onQuickAction,
  });

  @override
  State<FavorBalanceBubble> createState() => _FavorBalanceBubbleState();
}

class _FavorBalanceBubbleState extends State<FavorBalanceBubble> {
  ChatMessage get message => widget.message;

  static const _headerGradient = LinearGradient(
    colors: [Color(0xFF00695C), Color(0xFF26A69A)],
  );

  @override
  Widget build(BuildContext context) {
    final data = message.data ?? {};

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
                _buildBalanceSummary(context, data),
                const SizedBox(height: 8),
                _buildRecentRecords(context, data),
                _buildViewRecordsButton(context),
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

  List<Widget> _buildQuickActionsSection() {
    final actions = resolveQuickActions(message, 'favor_balance');
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
            child: const Icon(Icons.handshake, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              '人情往来',
              style: AppTextStyles.subtitle2.copyWith(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBalanceSummary(BuildContext context, Map<String, dynamic> data) {
    final received = data['total_received'] ?? data['received_count'] ?? 0;
    final given = data['total_given'] ?? data['given_count'] ?? 0;
    final pending = data['pending_count'] ?? 0;

    return Container(
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
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Expanded(
              child: _buildStatColumn(
                '收到',
                '$received',
                const Color(0xFFE91E63),
              ),
            ),
            Container(
              width: 1,
              height: 40,
              color: Theme.of(context).dividerColor,
            ),
            Expanded(
              child: _buildStatColumn(
                '送出',
                '$given',
                const Color(0xFF26A69A),
              ),
            ),
            if ((pending as num) > 0) ...[
              Container(
                width: 1,
                height: 40,
                color: Theme.of(context).dividerColor,
              ),
              Expanded(
                child: _buildStatColumn(
                  '待回',
                  '$pending',
                  AppColors.warning,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildStatColumn(String label, String value, Color color) {
    return Column(
      children: [
        Text(
          value,
          style: AppTextStyles.headline2.copyWith(
            color: color,
            fontWeight: FontWeight.bold,
            fontSize: 22,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: AppTextStyles.caption.copyWith(
            color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
          ),
        ),
      ],
    );
  }

  Widget _buildRecentRecords(BuildContext context, Map<String, dynamic> data) {
    final records = _extractRecords(data);
    if (records.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: records.take(3).map((record) {
        final name = (record['name'] ?? record['contact_name'] ?? '') as String;
        final type = (record['type'] ?? record['favor_type'] ?? '') as String;
        final amount = record['amount'];
        final date = record['date'] as String?;
        final isReceived = type == 'received' || type == '收到';

        return Container(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.75,
          ),
          margin: const EdgeInsets.only(bottom: 6),
          decoration: BoxDecoration(
            color: Theme.of(context).extension<AppColorsExtension>()!.cardBackground,
            borderRadius: BorderRadius.circular(8),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.03 * Theme.of(context).extension<AppColorsExtension>()!.shadowOpacity),
                blurRadius: 4,
                offset: const Offset(0, 1),
              ),
            ],
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              children: [
                Icon(
                  isReceived ? Icons.call_received : Icons.call_made,
                  size: 16,
                  color: isReceived ? const Color(0xFFE91E63) : const Color(0xFF26A69A),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name,
                        style: AppTextStyles.bodyText2.copyWith(
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      if (date != null)
                        Text(
                          _formatDateStr(date),
                          style: AppTextStyles.overline.copyWith(
                            color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                          ),
                        ),
                    ],
                  ),
                ),
                if (amount != null)
                  Text(
                    '${isReceived ? '+' : '-'}¥$amount',
                    style: AppTextStyles.subtitle2.copyWith(
                      color: isReceived ? const Color(0xFFE91E63) : const Color(0xFF26A69A),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  List<Map<String, dynamic>> _extractRecords(Map<String, dynamic> data) {
    if (data['records'] is List) {
      return (data['records'] as List)
          .whereType<Map<String, dynamic>>()
          .toList();
    }
    if (data['recent_records'] is List) {
      return (data['recent_records'] as List)
          .whereType<Map<String, dynamic>>()
          .toList();
    }
    return [];
  }

  String _formatDateStr(String dateStr) {
    try {
      final dt = DateTime.parse(dateStr);
      return '${dt.year}/${dt.month}/${dt.day}';
    } catch (_) {
      return dateStr;
    }
  }

  Widget _buildViewRecordsButton(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      child: OutlinedButton.icon(
        onPressed: () => context.push(Routes.favorLedger),
        icon: const Icon(Icons.receipt_long, size: 16),
        label: const Text('查看记录'),
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFF00695C),
          side: BorderSide(color: const Color(0xFF00695C).withValues(alpha: 0.3)),
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
