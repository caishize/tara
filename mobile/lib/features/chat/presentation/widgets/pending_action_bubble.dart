import 'package:flutter/material.dart';
import 'package:get_it/get_it.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../core/network/api_client.dart';
import '../../domain/entities/chat_message.dart';
import 'message_action_bar.dart';

/// A chat bubble widget that displays pending action confirmation cards
class PendingActionBubble extends StatefulWidget {
  final ChatMessage message;
  final void Function(String messageId)? onRegenerate;
  final void Function(String messageId, bool isLike, String? reason)? onFeedback;

  const PendingActionBubble({
    super.key,
    required this.message,
    this.onRegenerate,
    this.onFeedback,
  });

  @override
  State<PendingActionBubble> createState() => _PendingActionBubbleState();
}

class _PendingActionBubbleState extends State<PendingActionBubble> {
  bool _isConfirming = false;
  bool _isRejecting = false;
  String? _actionResult; // 'confirmed', 'rejected', or error message

  ChatMessage get message => widget.message;

  static const _headerGradient = LinearGradient(
    colors: [Color(0xFFF57F17), Color(0xFFFFA000)],
  );

  @override
  Widget build(BuildContext context) {
    final data = message.data ?? {};
    final display = data['display'] is Map<String, dynamic>
        ? data['display'] as Map<String, dynamic>
        : <String, dynamic>{};
    final actionId = (data['action_id'] ?? data['id'] ?? '') as String;
    final title = (display['title']
        ?? data['display_title']
        ?? data['title']
        ?? data['action_type']
        ?? '待确认操作') as String;
    final displayData = _extractDisplayData(data, display);
    final description = (display['description'] ?? data['description'] ?? '') as String;
    final expiresAt = data['expires_at'] as String?;

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
                _buildHeaderCard(context, title),
                const SizedBox(height: 8),
                _buildDetailsCard(context, displayData, description, expiresAt),
                const SizedBox(height: 8),
                if (_actionResult == null)
                  _buildConfirmRejectButtons(context, actionId)
                else
                  _buildResultBadge(),
                const SizedBox(height: 4),
                _buildMessageActionBar(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, String>> _extractDisplayData(
    Map<String, dynamic> data,
    Map<String, dynamic> display,
  ) {
    // 1. Try nested display.details (from PubSub confirm_card payload)
    if (display['details'] is List) {
      return _parseDetailsList(display['details'] as List);
    }
    // 2. Try top-level display_details (list of {label, value})
    if (data['display_details'] is List) {
      return _parseDetailsList(data['display_details'] as List);
    }
    // 3. Try display_data (map of key: value)
    if (data['display_data'] is Map) {
      return (data['display_data'] as Map).entries.map((e) {
        return {
          'label': e.key.toString(),
          'value': e.value.toString(),
        };
      }).toList();
    }
    return [];
  }

  List<Map<String, String>> _parseDetailsList(List items) {
    return items.map((item) {
      if (item is Map) {
        return {
          'label': (item['label'] ?? '').toString(),
          'value': (item['value'] ?? '').toString(),
        };
      }
      return {'label': '', 'value': item.toString()};
    }).toList();
  }

  Widget _buildHeaderCard(BuildContext context, String title) {
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
            child: const Icon(Icons.security, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '需要确认',
                  style: AppTextStyles.overline.copyWith(
                    color: Colors.white.withValues(alpha: 0.8),
                  ),
                ),
                Text(
                  title,
                  style: AppTextStyles.subtitle2.copyWith(color: Colors.white),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailsCard(
    BuildContext context,
    List<Map<String, String>> details,
    String description,
    String? expiresAt,
  ) {
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
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (description.isNotEmpty) ...[
              Text(
                description,
                style: AppTextStyles.bodyText2.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 8),
              Divider(height: 1, color: Theme.of(context).dividerColor),
              const SizedBox(height: 8),
            ],
            ...details.map((d) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 80,
                    child: Text(
                      d['label'] ?? '',
                      style: AppTextStyles.caption.copyWith(
                        color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                      ),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      d['value'] ?? '',
                      style: AppTextStyles.bodyText2.copyWith(
                        color: Theme.of(context).colorScheme.onSurface,
                      ),
                    ),
                  ),
                ],
              ),
            )),
            if (expiresAt != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(
                  children: [
                    Icon(Icons.timer_outlined, size: 14, color: AppColors.warning),
                    const SizedBox(width: 4),
                    Text(
                      _formatExpiry(expiresAt),
                      style: AppTextStyles.overline.copyWith(
                        color: AppColors.warning,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildConfirmRejectButtons(BuildContext context, String actionId) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      child: Row(
        children: [
          Expanded(
            child: OutlinedButton(
              onPressed: _isRejecting || _isConfirming
                  ? null
                  : () => _rejectAction(actionId),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.error,
                side: BorderSide(color: AppColors.error.withValues(alpha: 0.5)),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                padding: const EdgeInsets.symmetric(vertical: 10),
              ),
              child: _isRejecting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('拒绝'),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: ElevatedButton(
              onPressed: _isConfirming || _isRejecting
                  ? null
                  : () => _confirmAction(actionId),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.success,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                padding: const EdgeInsets.symmetric(vertical: 10),
              ),
              child: _isConfirming
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation(Colors.white),
                      ),
                    )
                  : const Text('确认执行'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResultBadge() {
    final isConfirmed = _actionResult == 'confirmed';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: isConfirmed
            ? AppColors.success.withValues(alpha: 0.1)
            : AppColors.error.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isConfirmed ? Icons.check_circle : Icons.cancel,
            size: 16,
            color: isConfirmed ? AppColors.success : AppColors.error,
          ),
          const SizedBox(width: 6),
          Text(
            isConfirmed ? '已确认执行' : '已拒绝',
            style: AppTextStyles.caption.copyWith(
              color: isConfirmed ? AppColors.success : AppColors.error,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmAction(String actionId) async {
    if (actionId.isEmpty) return;
    setState(() => _isConfirming = true);
    try {
      final apiClient = GetIt.instance<ApiClient>();
      await apiClient.post<Map<String, dynamic>>(
        '/actions/$actionId/confirm',
      );
      if (mounted) {
        setState(() {
          _isConfirming = false;
          _actionResult = 'confirmed';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isConfirming = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('确认失败: $e'),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
        );
      }
    }
  }

  Future<void> _rejectAction(String actionId) async {
    if (actionId.isEmpty) return;
    setState(() => _isRejecting = true);
    try {
      final apiClient = GetIt.instance<ApiClient>();
      await apiClient.post<Map<String, dynamic>>(
        '/actions/$actionId/reject',
      );
      if (mounted) {
        setState(() {
          _isRejecting = false;
          _actionResult = 'rejected';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isRejecting = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('拒绝失败: $e'),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
        );
      }
    }
  }

  String _formatExpiry(String isoTime) {
    try {
      final dt = DateTime.parse(isoTime).toLocal();
      final now = DateTime.now();
      final diff = dt.difference(now);
      if (diff.isNegative) return '已过期';
      if (diff.inMinutes < 60) return '${diff.inMinutes} 分钟后过期';
      if (diff.inHours < 24) return '${diff.inHours} 小时后过期';
      return '${diff.inDays} 天后过期';
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
        showCopy: false,
        showRegenerate: false,
        showFeedback: true,
        onFeedback: (isLike, reason) =>
            widget.onFeedback?.call(message.id, isLike, reason),
      ),
    );
  }
}
