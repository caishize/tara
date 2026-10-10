import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';

/// Time separator widget inserted between messages when gap > 30 minutes.
/// Displays format: "今天 09:00" or "昨天 14:30" or "01/15 10:00".
class TimeSeparator extends StatelessWidget {
  final DateTime timestamp;

  const TimeSeparator({super.key, required this.timestamp});

  String _formatTimestamp() {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));
    final messageDate = DateTime(timestamp.year, timestamp.month, timestamp.day);

    final timeStr =
        '${timestamp.hour.toString().padLeft(2, '0')}:${timestamp.minute.toString().padLeft(2, '0')}';

    if (messageDate == today) {
      return '今天 $timeStr';
    } else if (messageDate == yesterday) {
      return '昨天 $timeStr';
    } else if (now.year == timestamp.year) {
      return '${timestamp.month.toString().padLeft(2, '0')}/${timestamp.day.toString().padLeft(2, '0')} $timeStr';
    } else {
      return '${timestamp.year}/${timestamp.month.toString().padLeft(2, '0')}/${timestamp.day.toString().padLeft(2, '0')} $timeStr';
    }
  }

  @override
  Widget build(BuildContext context) {
    final dividerColor = Theme.of(context).dividerColor;
    final tertiaryColor = Theme.of(context).extension<AppColorsExtension>()!.textTertiary;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Row(
        children: [
          Expanded(child: Divider(color: dividerColor, height: 1)),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Text(
              _formatTimestamp(),
              style: TextStyle(
                fontSize: 12,
                color: tertiaryColor,
                fontWeight: FontWeight.w400,
              ),
            ),
          ),
          Expanded(child: Divider(color: dividerColor, height: 1)),
        ],
      ),
    );
  }
}
