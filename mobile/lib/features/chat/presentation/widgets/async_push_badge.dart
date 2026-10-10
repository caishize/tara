import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';

/// Small badge displayed on async push messages (briefing/discovery/reminder).
class AsyncPushBadge extends StatelessWidget {
  final String source; // "briefing" | "discovery" | "reminder"
  final DateTime? messageTime;

  const AsyncPushBadge({super.key, required this.source, this.messageTime});

  String get _label {
    switch (source) {
      case 'briefing':
        return _briefingLabel;
      case 'discovery':
        return '发现';
      case 'reminder':
        return '提醒';
      default:
        return '推送';
    }
  }

  String get _briefingLabel {
    final hour = (messageTime ?? DateTime.now()).hour;
    if (hour < 12) return '晨报';
    if (hour < 18) return '午报';
    return '晚报';
  }

  Color _backgroundColor(BuildContext context) {
    final ext = Theme.of(context).extension<AppColorsExtension>()!;
    switch (source) {
      case 'briefing':
        return ext.badgeBlue;
      case 'discovery':
        return ext.badgePurple;
      case 'reminder':
        return ext.badgeOrange;
      default:
        return ext.chipBackground;
    }
  }

  Color _textColor(BuildContext context) {
    switch (source) {
      case 'briefing':
        return const Color(0xFF1565C0);
      case 'discovery':
        return const Color(0xFF7B1FA2);
      case 'reminder':
        return const Color(0xFFE65100);
      default:
        return Theme.of(context).colorScheme.onSurfaceVariant;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      margin: const EdgeInsets.only(bottom: 4),
      decoration: BoxDecoration(
        color: _backgroundColor(context),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        _label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: _textColor(context),
        ),
      ),
    );
  }
}
