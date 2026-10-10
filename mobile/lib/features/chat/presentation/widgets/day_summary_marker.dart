import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';

/// Day boundary marker inserted between messages from different calendar days.
/// Shows the date as "M月d日·EEEE" and optionally a one-line day summary.
class DaySummaryMarker extends StatelessWidget {
  final DateTime date;
  final String? summary;

  const DaySummaryMarker({
    super.key,
    required this.date,
    this.summary,
  });

  String get _formattedDate {
    try {
      return DateFormat('M月d日·EEEE', 'zh_CN').format(date);
    } catch (_) {
      return DateFormat('M月d日').format(date);
    }
  }

  @override
  Widget build(BuildContext context) {
    final textColor =
        Theme.of(context).extension<AppColorsExtension>()?.textTertiary ??
            Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5);
    final dividerColor = Theme.of(context).dividerColor;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Column(
        children: [
          // Date line with flanking dividers
          Row(
            children: [
              Expanded(child: Divider(color: dividerColor, height: 1)),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Text(
                  _formattedDate,
                  style: TextStyle(
                    fontSize: 11,
                    color: textColor,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              Expanded(child: Divider(color: dividerColor, height: 1)),
            ],
          ),
          // Summary text — only rendered when non-empty
          if (summary != null && summary!.isNotEmpty) ...[
            const SizedBox(height: 4),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                summary!,
                style: TextStyle(
                  fontSize: 11,
                  color: textColor,
                  fontStyle: FontStyle.italic,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
