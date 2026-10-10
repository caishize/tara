import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';

/// Reusable section container for kanban view.
/// Shows an icon + title + optional count badge + optional chevron action.
class KanbanSection extends StatelessWidget {
  final String title;
  final int count;
  final IconData? icon;
  final Color? accentColor;
  final VoidCallback? onViewAll;
  final Widget child;
  /// When true, uses special "AI 智能洞察" styling with green text + white-on-green badge.
  final bool isAiSection;

  const KanbanSection({
    super.key,
    required this.title,
    required this.count,
    this.icon,
    this.accentColor,
    this.onViewAll,
    required this.child,
    this.isAiSection = false,
  });

  @override
  Widget build(BuildContext context) {
    if (count == 0) return const SizedBox.shrink();

    final tint = accentColor ?? AppColors.accentGreen;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
          child: Row(
            children: [
              if (icon != null) ...[
                Icon(icon, size: 16, color: tint),
                const SizedBox(width: 6),
              ],
              Text(
                title,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.5,
                  color: isAiSection
                      ? const Color(0xFF2D7A46)
                      : AppColors.textPrimary,
                ),
              ),
              if (count > 0) ...[
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: isAiSection
                        ? const Color(0xFF2D7A46)
                        : tint.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '$count',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: isAiSection ? Colors.white : tint,
                    ),
                  ),
                ),
              ],
              const Spacer(),
              if (onViewAll != null)
                GestureDetector(
                  onTap: onViewAll,
                  child: Icon(
                    Icons.chevron_right,
                    size: 20,
                    color: AppColors.textTertiary,
                  ),
                ),
            ],
          ),
        ),
        child,
      ],
    );
  }
}
