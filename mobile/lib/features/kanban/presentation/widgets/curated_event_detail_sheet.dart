import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/curated_event.dart';

/// Bottom sheet that displays full details for a curated event
/// when no dedicated detail page (e.g. TravelDetailPage) is available.
class CuratedEventDetailSheet extends StatelessWidget {
  final CuratedEvent event;

  const CuratedEventDetailSheet({super.key, required this.event});

  /// Show this sheet from any context.
  static Future<void> show(BuildContext context, CuratedEvent event) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        maxChildSize: 0.95,
        minChildSize: 0.4,
        builder: (_, scrollController) => CuratedEventDetailSheet(event: event),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        children: [
          _buildHandle(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              children: [
                _buildHeader(),
                const SizedBox(height: 16),
                _buildInfoSection(),
                if (event.belongsToTrip) ...[
                  const SizedBox(height: 16),
                  _buildTripContext(context),
                ],
                if (_userFacingNotes(event.notes) != null) ...[
                  const SizedBox(height: 16),
                  _buildNotes(context),
                ],
                if (event.dedupReason != null) ...[
                  const SizedBox(height: 16),
                  _buildAiSummary(),
                ],
                if (event.timelineItems.isNotEmpty) ...[
                  const SizedBox(height: 20),
                  _buildTimelineSection(),
                ],
                const SizedBox(height: 32),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHandle() {
    return Center(
      child: Container(
        width: 40,
        height: 4,
        margin: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: Colors.grey.shade300,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: _eventColor.withAlpha((0.1 * 255).round()),
            borderRadius: BorderRadius.circular(12),
          ),
          alignment: Alignment.center,
          child: Text(
            event.eventType?.icon ?? '📅',
            style: const TextStyle(fontSize: 24),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                event.title,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                event.eventType?.displayName ?? '事件',
                style: TextStyle(
                  fontSize: 14,
                  color: _eventColor,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildInfoSection() {
    return Column(
      children: [
        _buildInfoRow(Icons.schedule, '时间', _formatDateRange()),
        if (event.durationDays > 1)
          _buildInfoRow(Icons.timelapse, '时长', '${event.durationDays}天'),
        if (event.location != null)
          _buildInfoRow(Icons.location_on_outlined, '地点', event.location!),
        if (event.mergedCount > 1)
          _buildInfoRow(
            Icons.merge_type,
            '来源',
            '合并${event.mergedCount}个来源',
          ),
      ],
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppColors.textTertiary),
          const SizedBox(width: 10),
          SizedBox(
            width: 48,
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTripContext(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.accentBlue.withAlpha(15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.accentBlue.withAlpha(40)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.luggage_outlined, size: 16, color: AppColors.accentBlue),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  event.tripName ?? '',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.accentBlue,
                  ),
                ),
              ),
            ],
          ),
          if (event.tripDayLabel != null) ...[
            const SizedBox(height: 4),
            Padding(
              padding: const EdgeInsets.only(left: 22),
              child: Text(
                event.tripDayLabel!,
                style: TextStyle(
                  fontSize: 13,
                  color: AppColors.accentBlue.withAlpha(180),
                ),
              ),
            ),
          ],
          const SizedBox(height: 10),
          if (event.tripId != null)
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  final router = GoRouter.of(context);
                  final tripId = event.tripId!;
                  Navigator.pop(context);
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    router.push(Routes.tripDetail(tripId));
                  });
                },
                icon: const Icon(Icons.luggage_outlined, size: 16),
                label: const Text('查看行程详情'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.accentBlue,
                  side: const BorderSide(color: AppColors.accentBlue, width: 0.5),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  textStyle: const TextStyle(fontSize: 13),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildNotes(BuildContext context) {
    final cleaned = _userFacingNotes(event.notes)!;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.notes, size: 16, color: AppColors.textSecondary),
              SizedBox(width: 6),
              Text(
                '详情',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            cleaned,
            style: const TextStyle(
              fontSize: 14,
              color: AppColors.textPrimary,
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }

  static String? _userFacingNotes(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    final cleaned = raw
        .replaceAll(RegExp(r'\[随行程取消:.*?\]'), '')
        .replaceAll(RegExp(r'\[取消原因:.*?\]'), '')
        .trim();
    return cleaned.isEmpty ? null : cleaned;
  }

  Widget _buildAiSummary() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.primary.withAlpha((0.06 * 255).round()),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.auto_awesome, size: 16, color: AppColors.primary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              event.dedupReason!,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textSecondary,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTimelineSection() {
    final grouped = _groupTimelineItemsByDate();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '行程安排',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 12),
        ...grouped.entries.expand((entry) => [
              Padding(
                padding: const EdgeInsets.only(top: 8, bottom: 6),
                child: Text(
                  entry.key,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textSecondary,
                  ),
                ),
              ),
              ...entry.value.map(_buildTimelineItem),
            ]),
      ],
    );
  }

  Widget _buildTimelineItem(TimelineItem item) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 50,
            child: Text(
              _formatItemTime(item.time),
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textTertiary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Container(
            width: 8,
            height: 8,
            margin: const EdgeInsets.only(top: 5),
            decoration: BoxDecoration(
              color: item.confirmed ? AppColors.success : AppColors.warning,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.item,
                  style: TextStyle(
                    fontSize: 14,
                    color: item.confirmed
                        ? AppColors.textPrimary
                        : AppColors.textSecondary,
                  ),
                ),
                if (item.note != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    item.note!,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textTertiary,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (!item.confirmed)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.warning.withAlpha((0.1 * 255).round()),
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text(
                '待确认',
                style: TextStyle(fontSize: 10, color: AppColors.warning),
              ),
            ),
        ],
      ),
    );
  }

  Map<String, List<TimelineItem>> _groupTimelineItemsByDate() {
    final grouped = <String, List<TimelineItem>>{};
    int dayIndex = 0;

    for (final item in event.timelineItems) {
      String dateKey;
      try {
        final dt = DateTime.parse(item.time).toLocal();
        final formatted = DateFormat('M月d日 EEEE', 'zh_CN').format(dt);
        dateKey = 'Day ${dayIndex + 1} · $formatted';
        // Track date changes for day numbering
        if (!grouped.containsKey(dateKey)) {
          final existingDates = grouped.keys.toList();
          if (existingDates.isEmpty ||
              !existingDates.last.contains(DateFormat('M月d日').format(dt))) {
            dayIndex++;
            dateKey = 'Day $dayIndex · $formatted';
          }
        }
      } on FormatException {
        dateKey = '其他';
      }

      grouped.putIfAbsent(dateKey, () => []).add(item);
    }

    return grouped;
  }

  String _formatDateRange() {
    final dateFormat = DateFormat('M月d日');
    final localStart = event.startTime.toLocal();
    final localEnd = event.endTime?.toLocal();
    final startStr = dateFormat.format(localStart);
    if (localEnd == null) return startStr;
    return '$startStr - ${dateFormat.format(localEnd)}';
  }

  String _formatItemTime(String time) {
    try {
      final dt = DateTime.parse(time).toLocal();
      return DateFormat('HH:mm').format(dt);
    } on FormatException {
      return time;
    }
  }

  Color get _eventColor {
    final type = event.eventType;
    if (type == null) return AppColors.primary;
    return Color(type.colorValue);
  }
}
