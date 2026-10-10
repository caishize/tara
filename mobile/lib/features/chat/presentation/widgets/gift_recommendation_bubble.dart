import 'dart:math' show min;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../gifts/data/datasources/gift_remote_datasource.dart';
import '../../domain/entities/chat_message.dart';
import 'chat_bubble.dart' show buildQuickActionsRow;
import 'expandable_content_section.dart';
import 'message_action_bar.dart';

/// A chat bubble widget that displays gift recommendations as actionable cards.
///
/// Each gift item shows:
/// - Name, reason, and price (in red)
/// - Save/favorite toggle (heart icon)
/// - Purchase button (opens external browser)
///
/// Bottom actions:
/// - "Set purchase reminder" sends a message to trigger GiftTask creation
/// - "Get new recommendations" sends a message to trigger a new round
class GiftRecommendationBubble extends StatefulWidget {
  final ChatMessage message;
  final void Function(String messageId)? onRegenerate;
  final void Function(String messageId, bool isLike, String? reason)? onFeedback;
  final void Function(QuickAction action)? onQuickAction;

  const GiftRecommendationBubble({
    super.key,
    required this.message,
    this.onRegenerate,
    this.onFeedback,
    this.onQuickAction,
  });

  @override
  State<GiftRecommendationBubble> createState() => _GiftRecommendationBubbleState();
}

class _GiftRecommendationBubbleState extends State<GiftRecommendationBubble> {
  ChatMessage get message => widget.message;

  /// Track saved state per gift (by index, since chat gifts may not have IDs).
  final Map<int, bool> _savedStates = {};

  @override
  Widget build(BuildContext context) {
    final data = message.data ?? {};
    final memberName = data['member_name'] as String? ?? '家人';
    final age = data['age'] as int?;
    final ageGroup = data['age_group'] as String? ?? '';
    final memberId = data['member_id'] as String?;
    final recommendations = (data['recommendations'] as List<dynamic>?) ?? [];
    final memoryContext = data['memory_context'] as String?;
    final occasion = data['occasion'] as String?;

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
                _buildHeaderCard(
                  context, memberName, age, ageGroup, memberId,
                  memoryContext: memoryContext,
                  occasion: occasion,
                ),
                const SizedBox(height: 8),
                if (message.content.isNotEmpty && message.content.length > 20)
                  ExpandableContentSection(content: message.content),
                // Gift cards list
                ...List.generate(
                  min(recommendations.length, 3),
                  (index) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: _buildGiftCard(
                      context,
                      recommendations[index] as Map<String, dynamic>,
                      index,
                    ),
                  ),
                ),
                // View more button
                if (memberId != null)
                  _buildViewMoreButton(context, memberId, memberName),
                // Bottom action buttons
                _buildBottomActions(context, recommendations, memberName),
                const SizedBox(height: 4),
                _buildMessageActionBar(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBottomActions(
    BuildContext context,
    List<dynamic> recommendations,
    String memberName,
  ) {
    final actions = <QuickAction>[
      const QuickAction(
        label: '换一批推荐',
        action: '帮我换一批礼物推荐',
        type: 'message',
        icon: 'refresh',
      ),
    ];

    // Add purchase reminder action if there are recommendations
    if (recommendations.isNotEmpty) {
      final firstGift = recommendations[0] as Map<String, dynamic>;
      final giftName = firstGift['name'] as String? ?? '礼物';
      actions.insert(
        0,
        QuickAction(
          label: '设置购买提醒',
          action: '帮我设置购买提醒，$giftName',
          type: 'message',
          icon: 'alarm',
        ),
      );
    }

    // Merge with server-provided quick actions if any
    if (message.quickActions != null && message.quickActions!.isNotEmpty) {
      for (final qa in message.quickActions!) {
        final isDuplicate = actions.any((a) => a.action == qa.action);
        if (!isDuplicate) {
          actions.add(qa);
        }
      }
    }

    if (actions.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: buildQuickActionsRow(actions, onTap: widget.onQuickAction),
    );
  }

  Widget _buildMessageActionBar() {
    return MessageActionBar(
      createdAt: message.createdAt,
      config: MessageActionBarConfig(
        showCopy: true,
        showRegenerate: true,
        showFeedback: true,
        onCopy: () => _copyRecommendations(context),
        onRegenerate: widget.onRegenerate != null
            ? () => widget.onRegenerate!.call(message.id)
            : null,
        onFeedback: (isLike, reason) =>
            widget.onFeedback?.call(message.id, isLike, reason),
      ),
    );
  }

  void _copyRecommendations(BuildContext context) {
    HapticFeedback.lightImpact();
    final data = message.data ?? {};
    final memberName = data['member_name'] as String? ?? '家人';
    final recommendations = (data['recommendations'] as List<dynamic>?) ?? [];

    final buffer = StringBuffer();
    buffer.writeln('为 $memberName 推荐的礼物：\n');
    for (int i = 0; i < recommendations.length; i++) {
      final rec = recommendations[i] as Map<String, dynamic>;
      final name = rec['name'] as String? ?? '';
      final price = rec['price'] as num? ?? 0;
      final reason = rec['reason'] as String? ?? '';
      buffer.writeln('${i + 1}. $name - ¥${price.toStringAsFixed(0)}');
      if (reason.isNotEmpty) buffer.writeln('   $reason');
    }

    Clipboard.setData(ClipboardData(text: buffer.toString()));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Row(
          children: [
            Icon(Icons.check_circle, color: Colors.white, size: 18),
            SizedBox(width: 8),
            Text('推荐列表已复制'),
          ],
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        duration: const Duration(seconds: 2),
        margin: const EdgeInsets.all(16),
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

  Widget _buildHeaderCard(
    BuildContext context,
    String memberName,
    int? age,
    String ageGroup,
    String? memberId, {
    String? memoryContext,
    String? occasion,
  }) {
    final ageText = age != null ? '$age岁' : '';
    final infoParts = [ageText, ageGroup].where((s) => s.isNotEmpty).toList();
    if (occasion != null && occasion.isNotEmpty) {
      infoParts.add(occasion);
    }
    final subtitle = infoParts.join(' · ');

    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 20,
            backgroundColor: Colors.white.withValues(alpha: 0.2),
            child: Text(
              memberName.isNotEmpty ? memberName[0] : '?',
              style: AppTextStyles.subtitle1.copyWith(color: Colors.white),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '为 $memberName 推荐',
                  style: AppTextStyles.subtitle2.copyWith(color: Colors.white),
                ),
                if (subtitle.isNotEmpty)
                  Text(
                    subtitle,
                    style: AppTextStyles.caption.copyWith(
                      color: Colors.white.withValues(alpha: 0.8),
                    ),
                  ),
                if (memoryContext != null && memoryContext.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      children: [
                        Icon(
                          Icons.lightbulb_outline,
                          size: 12,
                          color: Colors.white.withValues(alpha: 0.9),
                        ),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            memoryContext,
                            style: AppTextStyles.caption.copyWith(
                              color: Colors.white.withValues(alpha: 0.9),
                              fontStyle: FontStyle.italic,
                              fontSize: 11,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.card_giftcard, color: Colors.white, size: 20),
          ),
        ],
      ),
    );
  }

  Widget _buildGiftCard(
    BuildContext context,
    Map<String, dynamic> gift,
    int index,
  ) {
    final name = gift['name'] as String? ?? '礼物';
    final price = gift['price'] as num? ?? 0;
    final reason = gift['reason'] as String? ?? '';
    final purchaseLink = gift['purchase_link'] as String?;
    final giftId = gift['id'] as String?;
    final isSaved = _savedStates[index] ?? (gift['is_saved'] as bool? ?? false);
    final theme = Theme.of(context);
    final ext = theme.extension<AppColorsExtension>()!;

    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      decoration: BoxDecoration(
        color: ext.cardBackground,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05 * ext.shadowOpacity),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          // Main gift info row
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
            child: Row(
              children: [
                // Gift icon
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: theme.colorScheme.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Center(
                    child: Text(
                      _getCategoryEmoji(name),
                      style: const TextStyle(fontSize: 24),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                // Gift name + reason
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name,
                        style: AppTextStyles.subtitle2.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (reason.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          reason,
                          style: AppTextStyles.caption.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                // Price (prominent, red)
                Text(
                  '¥${price.toStringAsFixed(0)}',
                  style: AppTextStyles.subtitle1.copyWith(
                    color: AppColors.error,
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ],
            ),
          ),
          // Action buttons row
          Container(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
            child: Row(
              children: [
                // Save/favorite button
                _buildCardActionButton(
                  icon: isSaved ? Icons.favorite : Icons.favorite_border,
                  label: isSaved ? '已收藏' : '收藏',
                  color: isSaved ? AppColors.error : theme.colorScheme.onSurfaceVariant,
                  onTap: () => _toggleSave(index, giftId, isSaved),
                ),
                const SizedBox(width: 8),
                // Purchase button
                if (purchaseLink != null)
                  _buildCardActionButton(
                    icon: Icons.shopping_cart_outlined,
                    label: '去购买',
                    color: theme.colorScheme.primary,
                    filled: true,
                    onTap: () => _openPurchaseUrl(context, purchaseLink, name),
                  ),
                const Spacer(),
                // Reminder button (sends chat message)
                _buildCardActionButton(
                  icon: Icons.alarm_outlined,
                  label: '提醒',
                  color: theme.colorScheme.onSurfaceVariant,
                  onTap: () {
                    widget.onQuickAction?.call(QuickAction(
                      label: '设置购买提醒',
                      action: '帮我设置购买提醒，$name',
                      type: 'message',
                    ));
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCardActionButton({
    required IconData icon,
    required String label,
    required Color color,
    bool filled = false,
    required VoidCallback onTap,
  }) {
    return Material(
      color: filled
          ? color.withValues(alpha: 0.1)
          : Colors.transparent,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: () {
          HapticFeedback.lightImpact();
          onTap();
        },
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 14, color: color),
              const SizedBox(width: 4),
              Text(
                label,
                style: AppTextStyles.caption.copyWith(
                  color: color,
                  fontWeight: filled ? FontWeight.w600 : FontWeight.normal,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _toggleSave(int index, String? giftId, bool currentlySaved) async {
    // Optimistic update
    setState(() {
      _savedStates[index] = !currentlySaved;
    });

    if (giftId == null) {
      // No gift ID — revert optimistic state, cannot persist without ID
      setState(() {
        _savedStates[index] = currentlySaved;
      });
      _showSnackBar(context, '暂不支持收藏此礼物', icon: Icons.info_outline);
      return;
    }

    try {
      final datasource = getIt<GiftRemoteDataSource>();
      if (!currentlySaved) {
        await datasource.saveGift(giftId);
      } else {
        await datasource.unsaveGift(giftId);
      }
      if (mounted) {
        _showSnackBar(
          context,
          !currentlySaved ? '已收藏' : '已取消收藏',
          icon: !currentlySaved ? Icons.favorite : Icons.favorite_border,
        );
      }
    } catch (e) {
      // Revert on failure
      if (mounted) {
        setState(() {
          _savedStates[index] = currentlySaved;
        });
        _showSnackBar(context, '操作失败，请重试', icon: Icons.error_outline);
      }
    }
  }

  void _showSnackBar(BuildContext context, String text, {IconData? icon}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            if (icon != null) ...[
              Icon(icon, color: Colors.white, size: 18),
              const SizedBox(width: 8),
            ],
            Text(text),
          ],
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        duration: const Duration(seconds: 2),
        margin: const EdgeInsets.all(16),
      ),
    );
  }

  Widget _buildViewMoreButton(BuildContext context, String memberId, String memberName) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      child: OutlinedButton.icon(
        onPressed: () {
          context.push(Routes.giftRecommend(memberId));
        },
        icon: const Icon(Icons.auto_awesome, size: 16),
        label: Text('查看$memberName的完整推荐'),
        style: OutlinedButton.styleFrom(
          foregroundColor: Theme.of(context).colorScheme.primary,
          side: BorderSide(color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.3)),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        ),
      ),
    );
  }

  String _getCategoryEmoji(String name) {
    final nameLower = name.toLowerCase();
    if (nameLower.contains('按摩') || nameLower.contains('足浴') || nameLower.contains('健康')) {
      return '💆';
    } else if (nameLower.contains('保健') || nameLower.contains('营养')) {
      return '💊';
    } else if (nameLower.contains('手环') || nameLower.contains('手表') || nameLower.contains('数码')) {
      return '⌚';
    } else if (nameLower.contains('围巾') || nameLower.contains('衣') || nameLower.contains('服装')) {
      return '🧣';
    } else if (nameLower.contains('茶') || nameLower.contains('酒')) {
      return '🍵';
    } else if (nameLower.contains('护肤') || nameLower.contains('化妆') || nameLower.contains('口红')) {
      return '💄';
    } else if (nameLower.contains('香水') || nameLower.contains('香薰')) {
      return '🌸';
    } else if (nameLower.contains('包') || nameLower.contains('钱包')) {
      return '👜';
    } else if (nameLower.contains('鞋')) {
      return '👟';
    } else if (nameLower.contains('书') || nameLower.contains('学习')) {
      return '📚';
    } else if (nameLower.contains('玩具') || nameLower.contains('游戏')) {
      return '🎮';
    } else if (nameLower.contains('运动')) {
      return '🏃';
    } else if (nameLower.contains('花') || nameLower.contains('甜品')) {
      return '💐';
    } else {
      return '🎁';
    }
  }

  Future<void> _openPurchaseUrl(BuildContext context, String url, String name) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('无法打开链接: $name'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }
}
