import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';

/// Three-tier dismiss options per design doc section 3.2.
///
/// Returns the selected feedback type string, or null if cancelled.
///
/// Options:
/// - "acknowledged" → "我知道了" (90-day snooze, satisfies obligation coverage)
/// - "not_useful" → "不感兴趣" (regen suppression window)
/// - "never" → "不再提醒此类" (permanent suppression)
class DismissBottomSheet {
  DismissBottomSheet._();

  static Future<String?> show(BuildContext context) {
    return showModalBottomSheet<String>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => const _DismissOptionsSheet(),
    );
  }
}

class _DismissOptionsSheet extends StatelessWidget {
  const _DismissOptionsSheet();

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '处理这条建议',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 16),
            _OptionTile(
              icon: Icons.check_circle_outline,
              iconColor: AppColors.accentGreen,
              title: '我知道了',
              subtitle: '不再主动提醒，90天后如有需要会再次出现',
              onTap: () => Navigator.of(context).pop('acknowledged'),
            ),
            const Divider(height: 1, color: AppColors.divider),
            _OptionTile(
              icon: Icons.not_interested,
              iconColor: AppColors.textTertiary,
              title: '不感兴趣',
              subtitle: '一段时间内不再出现此建议',
              onTap: () => Navigator.of(context).pop('not_useful'),
            ),
            const Divider(height: 1, color: AppColors.divider),
            _OptionTile(
              icon: Icons.block,
              iconColor: const Color(0xFFD32F2F),
              title: '不再提醒此类',
              subtitle: '永久屏蔽此类建议',
              onTap: () => Navigator.of(context).pop('never'),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: () => Navigator.of(context).pop(null),
              child: const Text(
                '取消',
                style: TextStyle(
                  fontSize: 14,
                  color: AppColors.textTertiary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OptionTile extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _OptionTile({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 4),
        child: Row(
          children: [
            Icon(icon, size: 22, color: iconColor),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textTertiary,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              size: 18,
              color: AppColors.textTertiary,
            ),
          ],
        ),
      ),
    );
  }
}
