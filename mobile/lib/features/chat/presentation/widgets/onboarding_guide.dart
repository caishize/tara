import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';

/// Conversational onboarding guide for new users.
/// Displays secretary avatar, welcome bubbles, and suggestion chips.
class OnboardingGuide extends StatefulWidget {
  final void Function(String prompt) onPromptTap;
  final void Function(String text) onFillInput;

  const OnboardingGuide({
    super.key,
    required this.onPromptTap,
    required this.onFillInput,
  });

  @override
  State<OnboardingGuide> createState() => _OnboardingGuideState();
}

class _OnboardingGuideState extends State<OnboardingGuide> {
  int _suggestionPage = 0;

  static const _allSuggestions = [
    // Page 0
    [
      '提醒我下周三给我妈打电话',
      '下周出差上海，帮我安排一下',
    ],
    // Page 1
    [
      '最近有家人生日快到了吗？',
      '帮我规划一个周末短途游',
    ],
    // Page 2
    [
      '今天天气怎么样？该穿什么？',
      '帮我看看这个月的人情往来',
    ],
  ];

  List<String> get _currentSuggestions =>
      _allSuggestions[_suggestionPage % _allSuggestions.length];

  void _cycleSuggestions() {
    setState(() {
      _suggestionPage = (_suggestionPage + 1) % _allSuggestions.length;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Secretary avatar + welcome bubble
          _buildSecretaryMessage(
            context,
            child: Text(
              '你好！我是你的生活秘书。\n你随便说，我来记、来安排、来提醒。',
              style: TextStyle(
                fontSize: 15,
                color: theme.colorScheme.onSurface,
                height: 1.6,
              ),
            ),
          ),
          const SizedBox(height: 12),
          // Context bubble (lighter green bg)
          _buildContextBubble(context),
          const SizedBox(height: 20),
          // "试试跟我说——" label
          Text(
            '试试跟我说——',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 12),
          // Suggestion chips (stacked vertically)
          _buildSuggestionChips(context),
          const SizedBox(height: 16),
          // Footer hint
          Center(
            child: Text(
              '随时跟我说就行，不用找菜单',
              style: TextStyle(
                fontSize: 12,
                color: theme.extension<AppColorsExtension>()!.textTertiary,
              ),
            ),
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildSecretaryAvatar() {
    return Container(
      width: 36,
      height: 36,
      decoration: const BoxDecoration(
        color: AppColors.primary,
        shape: BoxShape.circle,
      ),
      child: const Center(
        child: Text(
          '秘',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: Colors.white,
          ),
        ),
      ),
    );
  }

  Widget _buildSecretaryMessage(BuildContext context, {required Widget child}) {
    final ext = Theme.of(context).extension<AppColorsExtension>()!;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSecretaryAvatar(),
        const SizedBox(width: 10),
        Flexible(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: ext.assistantBubble,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(18),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(4),
                bottomRight: Radius.circular(18),
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.04 * ext.shadowOpacity),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: child,
          ),
        ),
      ],
    );
  }

  Widget _buildContextBubble(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.only(left: 46),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.primary.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          '看起来你日历里有待办事项，\n要我帮你留意什么吗？',
          style: TextStyle(
            fontSize: 14,
            color: theme.colorScheme.onSurface,
            height: 1.6,
          ),
        ),
      ),
    );
  }

  Widget _buildSuggestionChips(BuildContext context) {
    final primary = Theme.of(context).colorScheme.primary;
    final suggestions = _currentSuggestions;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // First chip on its own row
        if (suggestions.isNotEmpty)
          _buildChip(suggestions[0], primary),
        if (suggestions.length > 1) ...[
          const SizedBox(height: 8),
          // Second chip + "换一个" button in a row
          Row(
            children: [
              Flexible(child: _buildChip(suggestions[1], primary)),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: _cycleSuggestions,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: Theme.of(context).dividerColor),
                  ),
                  child: Text(
                    '换一个',
                    style: TextStyle(
                      fontSize: 13,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildChip(String text, Color primary) {
    return GestureDetector(
      onTap: () => widget.onFillInput(text),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: primary.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: primary.withValues(alpha: 0.2),
          ),
        ),
        child: Text(
          text,
          style: TextStyle(
            fontSize: 14,
            color: primary,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }
}
