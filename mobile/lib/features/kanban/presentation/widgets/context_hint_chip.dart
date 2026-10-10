import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';

/// 上下文提示组件 - 显示智能关联的原因
class ContextHintChip extends StatelessWidget {
  final String hint;
  final IconData? icon;
  final VoidCallback? onTap;

  const ContextHintChip({
    super.key,
    required this.hint,
    this.icon,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>();
    final colorScheme = Theme.of(context).colorScheme;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(top: 0),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: ext?.chipBackground ?? AppColors.chipBackground,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon ?? Icons.lightbulb_outline,
              size: 16,
              color: colorScheme.secondary,
            ),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                hint,
                style: TextStyle(
                  fontSize: 13,
                  color: colorScheme.onSurfaceVariant,
                  height: 1.4,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
