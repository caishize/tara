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

/// A chat bubble widget that displays member profile cards
class MemberProfileBubble extends StatefulWidget {
  final ChatMessage message;
  final void Function(String messageId)? onRegenerate;
  final void Function(String messageId, bool isLike, String? reason)? onFeedback;
  final void Function(QuickAction action)? onQuickAction;

  const MemberProfileBubble({
    super.key,
    required this.message,
    this.onRegenerate,
    this.onFeedback,
    this.onQuickAction,
  });

  @override
  State<MemberProfileBubble> createState() => _MemberProfileBubbleState();
}

class _MemberProfileBubbleState extends State<MemberProfileBubble> {
  ChatMessage get message => widget.message;

  static const _headerGradient = LinearGradient(
    colors: [Color(0xFFE65100), Color(0xFFFF9800)],
  );

  @override
  Widget build(BuildContext context) {
    final data = message.data ?? {};
    final members = _extractMembers(data);

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
                ...members.take(3).map((member) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _buildMemberCard(context, member),
                )),
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

  List<Map<String, dynamic>> _extractMembers(Map<String, dynamic> data) {
    if (data['members'] is List) {
      return (data['members'] as List)
          .whereType<Map<String, dynamic>>()
          .toList();
    }
    // Single member shape
    if (data['name'] != null || data['member_name'] != null) {
      return [data];
    }
    return [];
  }

  List<Widget> _buildQuickActionsSection() {
    final actions = resolveQuickActions(message, 'member_profile');
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
            child: const Icon(Icons.person, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              '家庭成员',
              style: AppTextStyles.subtitle2.copyWith(color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMemberCard(BuildContext context, Map<String, dynamic> member) {
    final name = (member['name'] ?? member['member_name'] ?? '成员') as String;
    final relation = member['relation'] as String?;
    final age = member['age'];
    final occupation = member['occupation'] as String?;
    final memberId = member['id'] as String? ?? member['member_id'] as String?;
    final preferences = _extractPreferences(member);

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
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: memberId != null
              ? () => context.push(Routes.memberDetail(memberId))
              : null,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 22,
                  backgroundColor: const Color(0xFFFF9800).withValues(alpha: 0.15),
                  child: Text(
                    name.isNotEmpty ? name[0] : '?',
                    style: AppTextStyles.subtitle1.copyWith(
                      color: const Color(0xFFE65100),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            name,
                            style: AppTextStyles.subtitle2.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          if (relation != null) ...[
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 1,
                              ),
                              decoration: BoxDecoration(
                                color: Theme.of(context).extension<AppColorsExtension>()!.badgeOrange,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                relation,
                                style: AppTextStyles.overline.copyWith(
                                  color: const Color(0xFFE65100),
                                  fontSize: 10,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          if (age != null)
                            Text(
                              '$age岁',
                              style: AppTextStyles.caption.copyWith(
                                color: Theme.of(context).colorScheme.onSurfaceVariant,
                              ),
                            ),
                          if (age != null && occupation != null)
                            Text(
                              ' · ',
                              style: AppTextStyles.caption.copyWith(
                                color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                              ),
                            ),
                          if (occupation != null)
                            Expanded(
                              child: Text(
                                occupation,
                                style: AppTextStyles.caption.copyWith(
                                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                        ],
                      ),
                      if (preferences.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Wrap(
                          spacing: 4,
                          runSpacing: 4,
                          children: preferences.take(3).map((tag) {
                            return Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: Theme.of(context).extension<AppColorsExtension>()!.chipBackground,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                tag,
                                style: AppTextStyles.overline.copyWith(
                                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                                  fontSize: 10,
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ],
                  ),
                ),
                if (memberId != null)
                  Icon(Icons.chevron_right, size: 20, color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary),
              ],
            ),
          ),
        ),
      ),
    );
  }

  List<String> _extractPreferences(Map<String, dynamic> member) {
    if (member['preferences'] is List) {
      return (member['preferences'] as List).map((e) => e.toString()).toList();
    }
    if (member['tags'] is List) {
      return (member['tags'] as List).map((e) => e.toString()).toList();
    }
    if (member['interests'] is List) {
      return (member['interests'] as List).map((e) => e.toString()).toList();
    }
    return [];
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
