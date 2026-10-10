import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

/// Displays structured key results from a tool execution.
///
/// Handles Lists (with bullet points), Maps (nested data), and scalar values.
/// Used by both the legacy tool execution section and the new ToolStepWidget.
class KeyResultsDisplay extends StatelessWidget {
  final Map<String, dynamic> keyResults;

  const KeyResultsDisplay({
    super.key,
    required this.keyResults,
  });

  @override
  Widget build(BuildContext context) {
    final widgets = <Widget>[];

    for (final entry in keyResults.entries) {
      final key = entry.key;
      final value = entry.value;

      if (key.startsWith('_')) continue;

      final displayKey = _formatKeyName(key);

      if (value is List) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(
              '$displayKey (${value.length}项)',
              style: AppTextStyles.overline.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        );
        for (var i = 0; i < value.length && i < 5; i++) {
          final item = value[i];
          if (item is Map) {
            final itemDisplay = _formatMapItem(item);
            widgets.add(
              Padding(
                padding: const EdgeInsets.only(left: 8, bottom: 2),
                child: Text(
                  '• $itemDisplay',
                  style: AppTextStyles.overline.copyWith(
                    color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            );
          } else {
            widgets.add(
              Padding(
                padding: const EdgeInsets.only(left: 8, bottom: 2),
                child: Text(
                  '• $item',
                  style: AppTextStyles.overline.copyWith(
                    color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                  ),
                ),
              ),
            );
          }
        }
        if (value.length > 5) {
          widgets.add(
            Padding(
              padding: const EdgeInsets.only(left: 8),
              child: Text(
                '... 还有 ${value.length - 5} 项',
                style: AppTextStyles.overline.copyWith(
                  color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
          );
        }
      } else if (value is Map) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 2),
            child: Text(
              '$displayKey: ${_formatMapItem(value)}',
              style: AppTextStyles.overline.copyWith(
                color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        );
      } else if (value != null) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 2),
            child: Text(
              '$displayKey: $value',
              style: AppTextStyles.overline.copyWith(
                color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
              ),
            ),
          ),
        );
      }
    }

    if (widgets.isEmpty) {
      return Text(
        '无详细信息',
        style: AppTextStyles.overline.copyWith(
          color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
          fontStyle: FontStyle.italic,
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: widgets,
    );
  }

  String _formatKeyName(String key) {
    const keyNames = {
      'total_count': '总数',
      'count': '数量',
      'recommendations': '推荐',
      'members': '成员',
      'dates': '日期',
      'itinerary': '行程',
      'destination': '目的地',
      'duration_days': '天数',
      'weather': '天气',
      'attractions': '景点',
      'activity_count': '活动数',
    };
    return keyNames[key] ?? key.replaceAll('_', ' ');
  }

  String _formatMapItem(Map? item) {
    if (item == null || item.isEmpty) {
      return '(空)';
    }

    final name = item['name'] ?? item['title'];
    final price = item['price'];
    final date = item['date'];
    final reason = item['reason'];

    final parts = <String>[];
    if (name != null && name.toString().isNotEmpty) {
      parts.add(name.toString());
    }
    if (price != null) {
      parts.add('¥$price');
    }
    if (date != null) {
      parts.add(date.toString());
    }
    if (reason != null && reason.toString().isNotEmpty) {
      final reasonStr = reason.toString();
      parts.add(reasonStr.length > 30 ? '${reasonStr.substring(0, 30)}...' : reasonStr);
    }

    if (parts.isEmpty) {
      for (final value in item.values) {
        if (value != null && value.toString().isNotEmpty) {
          final str = value.toString();
          return str.length > 50 ? '${str.substring(0, 50)}...' : str;
        }
      }
      return '(无显示内容)';
    }

    return parts.join(' · ');
  }
}
