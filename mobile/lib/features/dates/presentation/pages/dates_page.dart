import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/important_date.dart';
import '../bloc/dates_bloc.dart';
import '../widgets/date_card.dart';

class DatesPage extends StatefulWidget {
  const DatesPage({super.key});

  @override
  State<DatesPage> createState() => _DatesPageState();
}

class _DatesPageState extends State<DatesPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  DateType? _selectedType;
  late DateTime _selectedMonth;
  int? _selectedDay; // 选中的日期

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _selectedMonth = DateTime(DateTime.now().year, DateTime.now().month, 1);
    context.read<DatesBloc>().add(const DatesLoadRequested());
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/dashboard');
            }
          },
        ),
        title: Text('重要日期', style: AppTextStyles.headline5),
        actions: [_buildFilterButton()],
      ),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            _buildStatsRow(),
            _buildTabBar(),
            Expanded(child: _buildContent()),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => context.push('/dates/create'),
        backgroundColor: AppColors.primary,
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _buildStatsRow() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
      child: BlocBuilder<DatesBloc, DatesState>(
        builder: (context, state) {
          if (state is DatesLoaded) {
            final todayCount = state.todayDates.length;
            final weekCount = state.thisWeekDates.length;
            return Row(
              children: [
                if (todayCount > 0)
                  _buildStatChip('今天 $todayCount', AppColors.error),
                if (todayCount > 0) const SizedBox(width: 8),
                if (weekCount > 0)
                  _buildStatChip('本周 $weekCount', AppColors.warning),
              ],
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }

  Widget _buildStatChip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        label,
        style: AppTextStyles.caption.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildFilterButton() {
    return PopupMenuButton<DateType?>(
      icon: Icon(
        Icons.filter_list,
        color: _selectedType != null ? AppColors.primary : AppColors.textSecondary,
      ),
      onSelected: (type) {
        setState(() => _selectedType = type);
        context.read<DatesBloc>().add(DatesLoadRequested(dateType: type));
      },
      itemBuilder: (context) => [
        const PopupMenuItem(
          value: null,
          child: Text('全部类型'),
        ),
        ...DateType.values.map((type) => PopupMenuItem(
          value: type,
          child: Row(
            children: [
              Text(_getTypeEmoji(type)),
              const SizedBox(width: 8),
              Text(_getTypeName(type)),
            ],
          ),
        )),
      ],
    );
  }

  Widget _buildTabBar() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
      ),
      child: TabBar(
        controller: _tabController,
        indicator: BoxDecoration(
          color: AppColors.primary,
          borderRadius: BorderRadius.circular(10),
        ),
        labelColor: Colors.white,
        unselectedLabelColor: AppColors.textSecondary,
        labelStyle: AppTextStyles.bodyText2.copyWith(fontWeight: FontWeight.w600),
        dividerColor: Colors.transparent,
        tabs: const [
          Tab(text: '即将到来'),
          Tab(text: '全部日期'),
          Tab(text: '日历视图'),
        ],
      ),
    );
  }

  Widget _buildContent() {
    return BlocBuilder<DatesBloc, DatesState>(
      builder: (context, state) {
        if (state is DatesLoading) {
          return const Center(child: CircularProgressIndicator());
        }

        if (state is DatesError) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline,
                    size: 48, color: AppColors.textTertiary),
                const SizedBox(height: 16),
                Text(state.message, style: AppTextStyles.bodyText2),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () {
                    context.read<DatesBloc>().add(const DatesLoadRequested());
                  },
                  child: const Text('重试'),
                ),
              ],
            ),
          );
        }

        if (state is DatesLoaded) {
          return TabBarView(
            controller: _tabController,
            physics: const NeverScrollableScrollPhysics(), // Disable swipe to avoid confusion with bottom tabs
            children: [
              _buildUpcomingList(state.upcomingDates),
              _buildAllDatesList(state.dates),
              _buildCalendarView(state.dates),
            ],
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildUpcomingList(List<ImportantDate> dates) {
    if (dates.isEmpty) {
      return _buildEmptyState('暂无即将到来的日期', '点击右下角按钮添加重要日期');
    }

    // 按天数分组
    final todayDates = dates.where((d) => d.daysUntilNext == 0).toList();
    final thisWeekDates = dates
        .where((d) => d.daysUntilNext > 0 && d.daysUntilNext <= 7)
        .toList();
    final laterDates = dates.where((d) => d.daysUntilNext > 7).toList();

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (todayDates.isNotEmpty) ...[
          _buildSectionHeader('今天', AppColors.error),
          ...todayDates.map((d) => DateCard(date: d)),
          const SizedBox(height: 16),
        ],
        if (thisWeekDates.isNotEmpty) ...[
          _buildSectionHeader('本周', AppColors.warning),
          ...thisWeekDates.map((d) => DateCard(date: d)),
          const SizedBox(height: 16),
        ],
        if (laterDates.isNotEmpty) ...[
          _buildSectionHeader('稍后', AppColors.textSecondary),
          ...laterDates.map((d) => DateCard(date: d)),
        ],
      ],
    );
  }

  Widget _buildAllDatesList(List<ImportantDate> dates) {
    if (dates.isEmpty) {
      return _buildEmptyState('暂无重要日期', '点击右下角按钮添加重要日期');
    }

    // 按类型分组
    final groupedDates = <DateType, List<ImportantDate>>{};
    for (final date in dates) {
      groupedDates.putIfAbsent(date.dateType, () => []).add(date);
    }

    return ListView.builder(
      padding: const EdgeInsets.all(20),
      itemCount: groupedDates.length,
      itemBuilder: (context, index) {
        final type = groupedDates.keys.elementAt(index);
        final typeDates = groupedDates[type]!;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSectionHeader(
              '${_getTypeEmoji(type)} ${_getTypeName(type)}',
              AppColors.primary,
            ),
            ...typeDates.map((d) => DateCard(date: d)),
            const SizedBox(height: 16),
          ],
        );
      },
    );
  }

  Widget _buildCalendarView(List<ImportantDate> dates) {
    final now = DateTime.now();
    final daysInMonth = DateTime(_selectedMonth.year, _selectedMonth.month + 1, 0).day;
    final firstDayWeekday = DateTime(_selectedMonth.year, _selectedMonth.month, 1).weekday % 7;

    // 获取当月所有事件
    final monthEvents = _getEventsForMonth(dates, _selectedMonth);
    // 获取选中日期的事件
    final selectedDayEvents = _selectedDay != null
        ? _getEventsForDay(dates, _selectedMonth, _selectedDay!)
        : <ImportantDate>[];

    return Column(
      children: [
        // 月份切换头部
        _buildCalendarHeader(now),
        // 星期标题行
        _buildWeekdayHeader(),
        const SizedBox(height: 8),
        // 日历网格
        _buildCalendarGrid(dates, now, daysInMonth, firstDayWeekday),
        const SizedBox(height: 12),
        // 分隔线
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Divider(color: AppColors.textTertiary.withValues(alpha: 0.2)),
        ),
        // 事件列表区域
        Expanded(
          child: _selectedDay != null
              ? _buildSelectedDayEvents(selectedDayEvents)
              : _buildMonthEventsList(monthEvents),
        ),
      ],
    );
  }

  Widget _buildCalendarHeader(DateTime now) {
    final isCurrentMonth = _selectedMonth.year == now.year &&
        _selectedMonth.month == now.month;

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          IconButton(
            icon: const Icon(Icons.chevron_left),
            onPressed: () {
              setState(() {
                _selectedMonth = DateTime(
                  _selectedMonth.year,
                  _selectedMonth.month - 1,
                  1,
                );
                _selectedDay = null;
              });
            },
          ),
          GestureDetector(
            onTap: () {
              setState(() {
                _selectedMonth = DateTime(now.year, now.month, 1);
                _selectedDay = null;
              });
            },
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  DateFormat('yyyy年M月').format(_selectedMonth),
                  style: AppTextStyles.headline5,
                ),
                if (!isCurrentMonth) ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '回今天',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.chevron_right),
            onPressed: () {
              setState(() {
                _selectedMonth = DateTime(
                  _selectedMonth.year,
                  _selectedMonth.month + 1,
                  1,
                );
                _selectedDay = null;
              });
            },
          ),
        ],
      ),
    );
  }

  Widget _buildWeekdayHeader() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: ['日', '一', '二', '三', '四', '五', '六']
            .map((d) => SizedBox(
                  width: 40,
                  child: Text(
                    d,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ))
            .toList(),
      ),
    );
  }

  Widget _buildCalendarGrid(
    List<ImportantDate> dates,
    DateTime now,
    int daysInMonth,
    int firstDayWeekday,
  ) {
    final rows = ((daysInMonth + firstDayWeekday) / 7).ceil();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        children: List.generate(rows, (rowIndex) {
          return Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: List.generate(7, (colIndex) {
              final index = rowIndex * 7 + colIndex;
              if (index < firstDayWeekday || index >= daysInMonth + firstDayWeekday) {
                return const SizedBox(width: 40, height: 44);
              }

              final day = index - firstDayWeekday + 1;
              final isToday = _selectedMonth.year == now.year &&
                  _selectedMonth.month == now.month &&
                  day == now.day;
              final isSelected = _selectedDay == day;
              final dayEvents = _getEventsForDay(dates, _selectedMonth, day);
              final hasEvent = dayEvents.isNotEmpty;

              return GestureDetector(
                onTap: () {
                  setState(() {
                    _selectedDay = _selectedDay == day ? null : day;
                  });
                },
                onLongPress: () {
                  // 长按添加新日期
                  final selectedDate = DateTime(_selectedMonth.year, _selectedMonth.month, day);
                  context.push('/dates/create', extra: {'date': selectedDate});
                },
                child: Container(
                  width: 40,
                  height: 44,
                  margin: const EdgeInsets.all(2),
                  decoration: BoxDecoration(
                    color: isSelected
                        ? AppColors.primary
                        : isToday
                            ? AppColors.primary.withValues(alpha: 0.15)
                            : null,
                    borderRadius: BorderRadius.circular(10),
                    border: isToday && !isSelected
                        ? Border.all(color: AppColors.primary, width: 1.5)
                        : null,
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '$day',
                        style: AppTextStyles.bodyText2.copyWith(
                          color: isSelected
                              ? Colors.white
                              : isToday
                                  ? AppColors.primary
                                  : AppColors.textPrimary,
                          fontWeight: isToday || isSelected ? FontWeight.bold : null,
                        ),
                      ),
                      if (hasEvent)
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: dayEvents.take(3).map((e) {
                            return Container(
                              width: 5,
                              height: 5,
                              margin: const EdgeInsets.symmetric(horizontal: 1),
                              decoration: BoxDecoration(
                                color: isSelected
                                    ? Colors.white
                                    : _getEventColor(e.dateType),
                                shape: BoxShape.circle,
                              ),
                            );
                          }).toList(),
                        ),
                    ],
                  ),
                ),
              );
            }),
          );
        }),
      ),
    );
  }

  Widget _buildSelectedDayEvents(List<ImportantDate> events) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '${_selectedMonth.month}月$_selectedDay日',
                style: AppTextStyles.subtitle1.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              TextButton.icon(
                onPressed: () {
                  final selectedDate = DateTime(
                    _selectedMonth.year,
                    _selectedMonth.month,
                    _selectedDay!,
                  );
                  context.push('/dates/create', extra: {'date': selectedDate});
                },
                icon: const Icon(Icons.add, size: 18),
                label: const Text('添加'),
                style: TextButton.styleFrom(
                  foregroundColor: AppColors.primary,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: events.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(
                        Icons.event_available_outlined,
                        size: 48,
                        color: AppColors.textTertiary,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        '这天没有重要日期',
                        style: AppTextStyles.bodyText2.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextButton(
                        onPressed: () {
                          final selectedDate = DateTime(
                            _selectedMonth.year,
                            _selectedMonth.month,
                            _selectedDay!,
                          );
                          context.push('/dates/create', extra: {'date': selectedDate});
                        },
                        child: const Text('点击添加'),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  itemCount: events.length,
                  itemBuilder: (context, index) {
                    return _buildEventItem(events[index]);
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildMonthEventsList(List<ImportantDate> events) {
    if (events.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.event_note_outlined,
              size: 48,
              color: AppColors.textTertiary,
            ),
            const SizedBox(height: 12),
            Text(
              '本月没有重要日期',
              style: AppTextStyles.bodyText2.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '点击日期可添加',
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      );
    }

    // 按日期排序
    events.sort((a, b) => a.date.day.compareTo(b.date.day));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
          child: Text(
            '本月 ${events.length} 个重要日期',
            style: AppTextStyles.subtitle2.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            itemCount: events.length,
            itemBuilder: (context, index) {
              return _buildEventItem(events[index]);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildEventItem(ImportantDate event) {
    final color = _getEventColor(event.dateType);

    return GestureDetector(
      onTap: () async {
        await context.push('/dates/${event.id}');
        if (mounted) {
          context.read<DatesBloc>().add(const DatesLoadRequested());
        }
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.2)),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Center(
                child: Text(
                  event.dateTypeIcon,
                  style: const TextStyle(fontSize: 20),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    event.title,
                    style: AppTextStyles.subtitle2.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${event.dateDisplayString} · ${event.dateTypeName}',
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textTertiary,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }

  List<ImportantDate> _getEventsForMonth(List<ImportantDate> dates, DateTime month) {
    final daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    final matchedEvents = <ImportantDate>{};
    final seenTitles = <String, ImportantDate>{};  // 用于按标题去重

    // 检查这个月的每一天
    for (int day = 1; day <= daysInMonth; day++) {
      final solarDate = DateTime(month.year, month.month, day);
      for (final event in dates) {
        if (event.matchesDate(solarDate)) {
          // 对于重复事件，按标题去重（避免同一个节日出现多次）
          if (event.isRecurring) {
            final key = '${event.title}_${event.dateDisplayString}';
            if (!seenTitles.containsKey(key)) {
              seenTitles[key] = event;
              matchedEvents.add(event);
            }
          } else {
            matchedEvents.add(event);
          }
        }
      }
    }

    return matchedEvents.toList();
  }

  List<ImportantDate> _getEventsForDay(List<ImportantDate> dates, DateTime month, int day) {
    final solarDate = DateTime(month.year, month.month, day);
    final matchedEvents = dates.where((d) => d.matchesDate(solarDate)).toList();

    // 对于重复事件，按标题去重（避免同一个节日出现多次）
    final seenTitles = <String, ImportantDate>{};
    final dedupedEvents = <ImportantDate>[];

    for (final event in matchedEvents) {
      if (event.isRecurring) {
        final key = '${event.title}_${event.dateDisplayString}';
        if (!seenTitles.containsKey(key)) {
          seenTitles[key] = event;
          dedupedEvents.add(event);
        }
      } else {
        dedupedEvents.add(event);
      }
    }

    return dedupedEvents;
  }

  Color _getEventColor(DateType type) {
    switch (type) {
      case DateType.birthday:
        return const Color(0xFFE91E63); // 粉红
      case DateType.anniversary:
        return const Color(0xFFE53935); // 红色
      case DateType.holiday:
        return const Color(0xFFFF9800); // 橙色
      case DateType.memorial:
        return const Color(0xFF607D8B); // 灰蓝
      case DateType.custom:
        return AppColors.primary; // 主题色
    }
  }

  Widget _buildSectionHeader(String title, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 16,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          Text(title, style: AppTextStyles.subtitle2),
        ],
      ),
    );
  }

  Widget _buildEmptyState(String title, String subtitle) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.event_note_outlined,
              size: 64, color: AppColors.textTertiary),
          const SizedBox(height: 16),
          Text(title, style: AppTextStyles.subtitle1),
          const SizedBox(height: 8),
          Text(
            subtitle,
            style: AppTextStyles.bodyText2.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  String _getTypeName(DateType type) {
    switch (type) {
      case DateType.birthday:
        return '生日';
      case DateType.anniversary:
        return '纪念日';
      case DateType.holiday:
        return '节日';
      case DateType.memorial:
        return '祭日';
      case DateType.custom:
        return '自定义';
    }
  }

  String _getTypeEmoji(DateType type) {
    switch (type) {
      case DateType.birthday:
        return '🎂';
      case DateType.anniversary:
        return '💑';
      case DateType.holiday:
        return '🎉';
      case DateType.memorial:
        return '🕯️';
      case DateType.custom:
        return '📅';
    }
  }
}
