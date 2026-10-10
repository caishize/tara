import 'package:flutter/material.dart';

/// Reusable countdown pill badge showing time-relative labels.
/// "今天", "明天", "D-3", etc.
class CountdownBadge extends StatelessWidget {
  final DateTime targetDate;
  final Color? backgroundColor;
  final Color? textColor;
  final double fontSize;

  const CountdownBadge({
    super.key,
    required this.targetDate,
    this.backgroundColor,
    this.textColor,
    this.fontSize = 10,
  });

  @override
  Widget build(BuildContext context) {
    final label = _computeLabel();
    final bgColor = backgroundColor ?? Colors.white.withValues(alpha: 0.25);
    final fgColor = textColor ?? Colors.white;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: fontSize,
          fontWeight: FontWeight.w600,
          color: fgColor,
        ),
      ),
    );
  }

  String _computeLabel() {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final target = DateTime(targetDate.year, targetDate.month, targetDate.day);
    final diff = target.difference(today).inDays;

    if (diff == 0) return '今天';
    if (diff == 1) return '明天';
    if (diff == 2) return '后天';
    if (diff < 0) return '已过';
    return 'D-$diff';
  }
}
