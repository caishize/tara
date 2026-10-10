import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/di/injection.dart';
import '../../../../shared/widgets/timeline_item_card.dart';
import '../bloc/schedule_bloc.dart';
import '../bloc/schedule_event.dart';
import '../bloc/schedule_state.dart';
import '../../domain/entities/unified_event.dart';

/// Timeline page (时光轴).
/// Shows events grouped by date with segmented control.
class TimelinePage extends StatefulWidget {
  const TimelinePage({super.key});

  @override
  State<TimelinePage> createState() => _TimelinePageState();
}

class _TimelinePageState extends State<TimelinePage> {
  int _selectedSegment = 0; // Default to "未来" (all future events)
  late ScheduleBloc _scheduleBloc;
  DateTime _selectedDate = DateTime.now();

  @override
  void initState() {
    super.initState();
    _scheduleBloc = getIt<ScheduleBloc>();
    _scheduleBloc.add(const ScheduleLoadRequested());
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider.value(
      value: _scheduleBloc,
      child: Scaffold(
        backgroundColor: Theme.of(context).colorScheme.surface,
        body: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              _buildSegmentedControl(),
              Expanded(
                child: BlocBuilder<ScheduleBloc, ScheduleState>(
                  builder: (context, state) {
                    if (state is ScheduleLoading) {
                      return const Center(child: CircularProgressIndicator());
                    }

                    if (state is ScheduleError) {
                      return _buildErrorState(state.message);
                    }

                    if (state is ScheduleLoaded) {
                      return _buildTimeline(state);
                    }

                    return _buildEmptyState();
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '时光轴',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '过去与未来，一目了然',
                style: TextStyle(
                  fontSize: 14,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              boxShadow: AppColors.cardShadow,
            ),
            child: IconButton(
              icon: const Icon(Icons.calendar_month_outlined, color: AppColors.primary),
              onPressed: _showDatePicker,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSegmentedControl() {
    final ext = Theme.of(context).extension<AppColorsExtension>();

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: ext?.chipBackground ?? AppColors.chipBackground,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          _buildSegmentButton(0, '未来'),
          _buildSegmentButton(1, '历史'),
        ],
      ),
    );
  }

  Widget _buildSegmentButton(int index, String label) {
    final isSelected = _selectedSegment == index;

    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _selectedSegment = index),
        child: Container(
          margin: const EdgeInsets.all(4),
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: isSelected ? Colors.white : Colors.transparent,
            borderRadius: BorderRadius.circular(10),
            boxShadow: isSelected ? [AppColors.shadowLight] : null,
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            style: TextStyle(
              fontSize: 14,
              fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
              color: isSelected
                  ? Theme.of(context).colorScheme.onSurface
                  : Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTimeline(ScheduleLoaded state) {
    final events = _getEventsForSegment(state);

    if (events.isEmpty) {
      return _buildEmptyState();
    }

    // Group events by date
    // PRD 2.2.4: 历史Tab(segment=1)倒排, 未来Tab(segment=0)正排
    final isHistoryTab = _selectedSegment == 1;
    final groupedEvents = _groupEventsByDate(events, descending: isHistoryTab);

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: groupedEvents.length,
      itemBuilder: (context, index) {
        final entry = groupedEvents.entries.elementAt(index);
        final date = entry.key;
        final dateEvents = entry.value;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildDateHeader(date),
            ...dateEvents.map((event) => _buildEventCard(event)),
          ],
        );
      },
    );
  }

  Widget _buildDateHeader(DateTime date) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final eventDate = DateTime(date.year, date.month, date.day);
    final daysDiff = eventDate.difference(today).inDays;

    final isToday = daysDiff == 0;
    String? tagLabel = _getDateTagLabel(daysDiff, date);
    String dateStr = DateFormat('M月d日').format(date);
    String weekdayStr = _getChineseWeekday(date);

    return TimelineDateHeader(
      date: dateStr,
      weekday: weekdayStr,
      tagLabel: tagLabel,
      isToday: isToday,
    );
  }

  String? _getDateTagLabel(int daysDiff, DateTime date) {
    if (daysDiff == 0) return '今天';
    if (daysDiff == 1) return '明天';
    if (daysDiff == -1) return '昨天';
    if (daysDiff >= 2 && daysDiff <= 6) {
      // This week (remaining days)
      return null; // No tag for this week days
    }
    if (daysDiff >= 7 && daysDiff <= 13) {
      return '下周${_getChineseWeekdayShort(date)}';
    }
    if (daysDiff < -1 && daysDiff >= -7) {
      return '上周${_getChineseWeekdayShort(date)}';
    }
    return null;
  }

  String _getChineseWeekday(DateTime date) {
    const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    return weekdays[date.weekday - 1];
  }

  String _getChineseWeekdayShort(DateTime date) {
    const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
    return weekdays[date.weekday - 1];
  }

  Widget _buildEventCard(UnifiedEvent event) {
    // Travel plans and important dates use the reminder card style
    final isSpecialEvent = event.source == EventSource.importantDate ||
        event.source == EventSource.travelPlan;

    if (isSpecialEvent) {
      return TimelineReminderCard(
        title: event.title,
        subtitle: _buildEventSubtitle(event),
        accentColor: Color(event.color.value),
        icon: _getIconForEvent(event),
        onTap: () => _navigateToEventDetail(event),
        eventId: event.id,
        onDelete: () => _scheduleBloc.add(ScheduleCancelEventRequested(
          eventId: event.id,
          eventTitle: event.title,
          sourceType: event.source.name,
        )),
      );
    }

    // Regular scheduled events
    String? time;
    String? amPm;

    if (event.dateTime != null && !event.isAllDay) {
      final localDateTime = event.dateTime!.toLocal();
      time = DateFormat('HH:mm').format(localDateTime);
      amPm = DateFormat('a').format(localDateTime).toUpperCase();
    }

    return TimelineItemCard(
      title: event.title,
      subtitle: _buildScheduleSubtitle(event),
      time: time,
      amPm: amPm,
      accentColor: AppColors.warning, // Orange accent for scheduled events
      onTap: () => _navigateToEventDetail(event),
      eventId: event.id,
      onDelete: () => _scheduleBloc.add(ScheduleCancelEventRequested(
        eventId: event.id,
        eventTitle: event.title,
        sourceType: event.source.name,
      )),
    );
  }

  String _buildEventSubtitle(UnifiedEvent event) {
    final parts = <String>[];

    // Duration info
    if (event.endDateTime != null && event.dateTime != null) {
      final days = event.endDateTime!.difference(event.dateTime!).inDays + 1;
      if (days > 1) {
        parts.add('${days}天');
      }
    }

    // Countdown
    if (event.dateTime != null) {
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final localDateTime = event.dateTime!.toLocal();
      final eventDate = DateTime(localDateTime.year, localDateTime.month, localDateTime.day);
      final daysUntil = eventDate.difference(today).inDays;

      if (daysUntil > 0) {
        parts.add('倒计时${daysUntil}天');
      }
    }

    // AI insights or description
    if (event.aiInsights.isNotEmpty) {
      parts.add(event.aiInsights.first);
    } else if (event.description != null && event.description!.isNotEmpty) {
      parts.add(event.description!);
    }

    return parts.join('·');
  }

  String? _buildScheduleSubtitle(UnifiedEvent event) {
    final parts = <String>[];

    if (event.location != null && event.location!.isNotEmpty) {
      parts.add(event.location!);
    }

    // Calculate duration if end time is available
    if (event.endDateTime != null && event.dateTime != null) {
      final duration = event.endDateTime!.difference(event.dateTime!);
      if (duration.inMinutes > 0) {
        if (duration.inHours > 0) {
          parts.add('${duration.inHours}小时');
        } else {
          parts.add('${duration.inMinutes}分钟');
        }
      }
    }

    return parts.isEmpty ? event.description : parts.join('·');
  }

  IconData _getIconForEvent(UnifiedEvent event) {
    switch (event.source) {
      case EventSource.importantDate:
        return Icons.card_giftcard;
      case EventSource.travelPlan:
        return Icons.flight_takeoff;
      case EventSource.familyTask:
        return Icons.check_circle_outline;
      case EventSource.extractedSchedule:
        return Icons.event;
      case EventSource.extractedPlan:
        return Icons.task_alt;
      case EventSource.externalCalendar:
        return Icons.calendar_today;
      case EventSource.externalTravel:
        return Icons.confirmation_number;
    }
  }

  Future<void> _navigateToEventDetail(UnifiedEvent event) async {
    switch (event.source) {
      case EventSource.travelPlan:
        final tripId = event.sourceData['tripId'] as String? ??
            event.sourceData['originalId'] as String?;
        if (tripId != null) {
          await context.push(Routes.tripDetail(tripId));
        }
        break;
      case EventSource.importantDate:
        final dateId = event.sourceData['dateId'] as String? ??
            event.sourceData['originalId'] as String?;
        if (dateId != null) {
          await context.push(Routes.dateDetail(dateId));
        }
        break;
      default:
        break;
    }
    if (mounted) {
      _scheduleBloc.add(const ScheduleLoadRequested());
    }
  }

  Map<DateTime, List<UnifiedEvent>> _groupEventsByDate(List<UnifiedEvent> events, {bool descending = false}) {
    final grouped = <DateTime, List<UnifiedEvent>>{};

    for (final event in events) {
      if (event.dateTime == null) continue;

      // Convert to local time for grouping
      final localDateTime = event.dateTime!.toLocal();
      final date = DateTime(
        localDateTime.year,
        localDateTime.month,
        localDateTime.day,
      );

      grouped.putIfAbsent(date, () => []).add(event);
    }

    // Sort by date - ascending for future, descending for history
    // PRD 2.2.4: 历史Tab倒排(今天在上,往下越来越早), 未来Tab正排(今天在上,往下越来越远)
    final sortedEntries = grouped.entries.toList()
      ..sort((a, b) => descending
          ? b.key.compareTo(a.key)  // Descending: newest first (for history)
          : a.key.compareTo(b.key)); // Ascending: soonest first (for future)

    return Map.fromEntries(sortedEntries);
  }

  List<UnifiedEvent> _getEventsForSegment(ScheduleLoaded state) {
    final allEvents = state.allEvents;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    switch (_selectedSegment) {
      case 0: // 未来 - All future events (today and onwards)
        return allEvents.where((e) {
          if (e.dateTime == null) return false;
          // Convert to local time before extracting date components
          final localDateTime = e.dateTime!.toLocal();
          final eventDate = DateTime(localDateTime.year, localDateTime.month, localDateTime.day);
          return !eventDate.isBefore(today);
        }).toList()
          ..sort((a, b) => (a.dateTime ?? DateTime.now()).compareTo(b.dateTime ?? DateTime.now()));

      case 1: // 历史 - Past events (before today)
        return allEvents.where((e) {
          if (e.dateTime == null) return false;
          // Convert to local time before extracting date components
          final localDateTime = e.dateTime!.toLocal();
          final eventDate = DateTime(localDateTime.year, localDateTime.month, localDateTime.day);
          return eventDate.isBefore(today);
        }).toList()
          ..sort((a, b) => (b.dateTime ?? DateTime.now()).compareTo(a.dateTime ?? DateTime.now()));

      default:
        return [];
    }
  }

  Future<void> _showDatePicker() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(now.year - 5),
      lastDate: DateTime(now.year + 5),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: ColorScheme.light(
              primary: AppColors.primary,
              onPrimary: Colors.white,
              surface: Colors.white,
              onSurface: AppColors.textPrimary,
            ),
          ),
          child: child!,
        );
      },
    );

    if (picked != null && picked != _selectedDate) {
      setState(() {
        _selectedDate = picked;
        // Determine which segment the selected date falls into
        final now = DateTime.now();
        final today = DateTime(now.year, now.month, now.day);
        final pickedDate = DateTime(picked.year, picked.month, picked.day);

        if (pickedDate.isBefore(today)) {
          _selectedSegment = 1; // 历史
        } else {
          _selectedSegment = 0; // 未来
        }
      });
    }
  }

  Widget _buildEmptyState() {
    String message;
    switch (_selectedSegment) {
      case 0:
        message = '未来暂无安排';
        break;
      case 1:
        message = '暂无历史记录';
        break;
      default:
        message = '暂无事件';
    }

    final colorScheme = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<AppColorsExtension>();

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.event_note_outlined,
            size: 64,
            color: ext?.textTertiary ?? AppColors.textTertiary,
          ),
          const SizedBox(height: 16),
          Text(
            message,
            style: TextStyle(
              fontSize: 16,
              color: colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: () => context.push(Routes.tripCreate),
            child: Text(
              '添加第一个事件',
              style: TextStyle(
                fontSize: 14,
                color: AppColors.primary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState(String message) {
    final errColorScheme = Theme.of(context).colorScheme;
    final errExt = Theme.of(context).extension<AppColorsExtension>();

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.error_outline,
            size: 64,
            color: errExt?.textTertiary ?? AppColors.textTertiary,
          ),
          const SizedBox(height: 16),
          Text(
            message,
            style: TextStyle(
              fontSize: 16,
              color: errColorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () {
              _scheduleBloc.add(const ScheduleRefreshRequested());
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
            ),
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }
}
