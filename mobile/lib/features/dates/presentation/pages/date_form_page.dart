import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/utils/lunar_utils.dart';
import '../../domain/entities/important_date.dart';
import '../bloc/dates_bloc.dart';

class DateFormPage extends StatefulWidget {
  final ImportantDate? date;

  const DateFormPage({super.key, this.date});

  @override
  State<DateFormPage> createState() => _DateFormPageState();
}

class _DateFormPageState extends State<DateFormPage> {
  late TextEditingController _titleController;
  late TextEditingController _descriptionController;
  DateTime _selectedDate = DateTime.now();
  DateType _selectedType = DateType.birthday;
  CalendarType _calendarType = CalendarType.solar;
  bool _isRecurring = true;
  List<int> _reminderDays = [0, 1, 7];

  // 农历相关
  int _lunarMonth = 1;
  int _lunarDay = 1;

  bool get _isEditing => widget.date != null;

  @override
  void initState() {
    super.initState();
    _titleController = TextEditingController(text: widget.date?.title ?? '');
    _descriptionController =
        TextEditingController(text: widget.date?.description ?? '');

    if (widget.date != null) {
      _selectedDate = widget.date!.date;
      _selectedType = widget.date!.dateType;
      _calendarType = widget.date!.calendarType;
      _isRecurring = widget.date!.isRecurring;
      _reminderDays = widget.date!.reminderDays;

      // 初始化农历数据
      if (widget.date!.lunarMonth != null && widget.date!.lunarDay != null) {
        _lunarMonth = widget.date!.lunarMonth!;
        _lunarDay = widget.date!.lunarDay!;
      } else {
        // 从公历日期推算农历
        final lunar = LunarUtils.solarToLunar(_selectedDate);
        _lunarMonth = lunar.getMonth();
        _lunarDay = lunar.getDay();
      }
    } else {
      // 新建时，用当前日期的农历
      final lunar = LunarUtils.solarToLunar(_selectedDate);
      _lunarMonth = lunar.getMonth();
      _lunarDay = lunar.getDay();
    }
  }

  @override
  void dispose() {
    _titleController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(_isEditing ? '编辑日期' : '添加日期'),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          TextButton(
            onPressed: _saveDate,
            child: Text(
              '保存',
              style: AppTextStyles.bodyText1.copyWith(
                color: AppColors.primary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
      body: BlocListener<DatesBloc, DatesState>(
        listener: (context, state) {
          if (state is DateOperationSuccess) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.message)),
            );
            context.pop();
          } else if (state is DatesError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          }
        },
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildTitleField(),
              const SizedBox(height: 20),
              _buildDatePicker(),
              const SizedBox(height: 20),
              _buildTypeSelector(),
              const SizedBox(height: 20),
              _buildCalendarTypeSelector(),
              const SizedBox(height: 20),
              _buildRecurringSwitch(),
              const SizedBox(height: 20),
              _buildReminderSettings(),
              const SizedBox(height: 20),
              _buildDescriptionField(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTitleField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('标题', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        TextField(
          controller: _titleController,
          decoration: InputDecoration(
            hintText: '例如：妈妈的生日',
            filled: true,
            fillColor: Colors.white,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 14,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDatePicker() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('日期', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        if (_calendarType == CalendarType.solar)
          _buildSolarDatePicker()
        else
          _buildLunarDatePicker(),
      ],
    );
  }

  Widget _buildSolarDatePicker() {
    return InkWell(
      onTap: _pickDate,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            const Icon(Icons.calendar_today, color: AppColors.primary),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  DateFormat('yyyy年M月d日').format(_selectedDate),
                  style: AppTextStyles.bodyText1,
                ),
                Text(
                  LunarUtils.getLunarDateString(_selectedDate),
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
            const Spacer(),
            const Icon(Icons.chevron_right, color: AppColors.textSecondary),
          ],
        ),
      ),
    );
  }

  Widget _buildLunarDatePicker() {
    final monthName = LunarUtils.getLunarMonthName(_lunarMonth);
    final dayName = LunarUtils.getLunarDayName(_lunarDay);

    return InkWell(
      onTap: _pickLunarDate,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            const Icon(Icons.brightness_3, color: AppColors.primary),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '农历$monthName$dayName',
                  style: AppTextStyles.bodyText1,
                ),
                Text(
                  '对应公历: ${DateFormat('M月d日').format(LunarUtils.lunarToSolar(DateTime.now().year, _lunarMonth, _lunarDay))}',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
            const Spacer(),
            const Icon(Icons.chevron_right, color: AppColors.textSecondary),
          ],
        ),
      ),
    );
  }

  Widget _buildTypeSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('类型', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: DateType.values.map((type) {
            final isSelected = _selectedType == type;
            return ChoiceChip(
              label: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(_getTypeEmoji(type)),
                  const SizedBox(width: 4),
                  Text(_getTypeName(type)),
                ],
              ),
              selected: isSelected,
              onSelected: (selected) {
                if (selected) {
                  setState(() => _selectedType = type);
                }
              },
              selectedColor: AppColors.primary.withValues(alpha: 0.2),
              backgroundColor: Colors.white,
              labelStyle: TextStyle(
                color: isSelected ? AppColors.primary : AppColors.textPrimary,
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildCalendarTypeSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('日历类型', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: _buildCalendarOption(
                '公历',
                CalendarType.solar,
                Icons.calendar_today,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildCalendarOption(
                '农历',
                CalendarType.lunar,
                Icons.brightness_3,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildCalendarOption(
    String label,
    CalendarType type,
    IconData icon,
  ) {
    final isSelected = _calendarType == type;
    return InkWell(
      onTap: () => setState(() => _calendarType = type),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary.withValues(alpha: 0.1) : Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? AppColors.primary : Colors.transparent,
            width: 2,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              color: isSelected ? AppColors.primary : AppColors.textSecondary,
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: AppTextStyles.bodyText1.copyWith(
                color: isSelected ? AppColors.primary : AppColors.textPrimary,
                fontWeight: isSelected ? FontWeight.w600 : null,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecurringSwitch() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.repeat, color: AppColors.textSecondary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('每年重复', style: AppTextStyles.bodyText1),
                Text(
                  '自动添加到每年的日程',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: _isRecurring,
            onChanged: (value) => setState(() => _isRecurring = value),
            activeColor: AppColors.primary,
          ),
        ],
      ),
    );
  }

  Widget _buildReminderSettings() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('提醒设置', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [0, 1, 3, 7, 14, 30].map((days) {
            final isSelected = _reminderDays.contains(days);
            return FilterChip(
              label: Text(_getReminderLabel(days)),
              selected: isSelected,
              onSelected: (selected) {
                setState(() {
                  if (selected) {
                    _reminderDays.add(days);
                  } else {
                    _reminderDays.remove(days);
                  }
                });
              },
              selectedColor: AppColors.primary.withValues(alpha: 0.2),
              backgroundColor: Colors.white,
              checkmarkColor: AppColors.primary,
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildDescriptionField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('备注', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        TextField(
          controller: _descriptionController,
          maxLines: 3,
          decoration: InputDecoration(
            hintText: '添加备注信息...',
            filled: true,
            fillColor: Colors.white,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
            contentPadding: const EdgeInsets.all(16),
          ),
        ),
      ],
    );
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(1900),
      lastDate: DateTime(2100),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.light(
              primary: AppColors.primary,
            ),
          ),
          child: child!,
        );
      },
    );

    if (picked != null) {
      setState(() {
        _selectedDate = picked;
        // 同步更新农历
        final lunar = LunarUtils.solarToLunar(picked);
        _lunarMonth = lunar.getMonth();
        _lunarDay = lunar.getDay();
      });
    }
  }

  Future<void> _pickLunarDate() async {
    await showModalBottomSheet(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        int tempMonth = _lunarMonth;
        int tempDay = _lunarDay;

        return StatefulBuilder(
          builder: (context, setModalState) {
            return Container(
              padding: const EdgeInsets.all(20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text(
                          '取消',
                          style: TextStyle(color: AppColors.textSecondary),
                        ),
                      ),
                      Text(
                        '选择农历日期',
                        style: AppTextStyles.subtitle1.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      TextButton(
                        onPressed: () {
                          setState(() {
                            _lunarMonth = tempMonth;
                            _lunarDay = tempDay;
                            // 更新对应的公历日期
                            _selectedDate = LunarUtils.lunarToSolar(
                              DateTime.now().year,
                              tempMonth,
                              tempDay,
                            );
                          });
                          Navigator.pop(context);
                        },
                        child: const Text(
                          '确定',
                          style: TextStyle(
                            color: AppColors.primary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('月份', style: AppTextStyles.caption),
                            const SizedBox(height: 8),
                            Container(
                              height: 150,
                              decoration: BoxDecoration(
                                border: Border.all(color: AppColors.textTertiary.withValues(alpha: 0.3)),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: ListWheelScrollView.useDelegate(
                                itemExtent: 40,
                                perspective: 0.005,
                                diameterRatio: 1.2,
                                physics: const FixedExtentScrollPhysics(),
                                controller: FixedExtentScrollController(
                                  initialItem: tempMonth - 1,
                                ),
                                onSelectedItemChanged: (index) {
                                  setModalState(() {
                                    tempMonth = index + 1;
                                    // 确保日期有效
                                    if (tempDay > 30) tempDay = 30;
                                  });
                                },
                                childDelegate: ListWheelChildBuilderDelegate(
                                  childCount: 12,
                                  builder: (context, index) {
                                    final month = index + 1;
                                    final isSelected = month == tempMonth;
                                    return Center(
                                      child: Text(
                                        LunarUtils.getLunarMonthName(month),
                                        style: AppTextStyles.bodyText1.copyWith(
                                          color: isSelected
                                              ? AppColors.primary
                                              : AppColors.textPrimary,
                                          fontWeight: isSelected
                                              ? FontWeight.w600
                                              : null,
                                        ),
                                      ),
                                    );
                                  },
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('日期', style: AppTextStyles.caption),
                            const SizedBox(height: 8),
                            Container(
                              height: 150,
                              decoration: BoxDecoration(
                                border: Border.all(color: AppColors.textTertiary.withValues(alpha: 0.3)),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: ListWheelScrollView.useDelegate(
                                itemExtent: 40,
                                perspective: 0.005,
                                diameterRatio: 1.2,
                                physics: const FixedExtentScrollPhysics(),
                                controller: FixedExtentScrollController(
                                  initialItem: tempDay - 1,
                                ),
                                onSelectedItemChanged: (index) {
                                  setModalState(() => tempDay = index + 1);
                                },
                                childDelegate: ListWheelChildBuilderDelegate(
                                  childCount: 30,
                                  builder: (context, index) {
                                    final day = index + 1;
                                    final isSelected = day == tempDay;
                                    return Center(
                                      child: Text(
                                        LunarUtils.getLunarDayName(day),
                                        style: AppTextStyles.bodyText1.copyWith(
                                          color: isSelected
                                              ? AppColors.primary
                                              : AppColors.textPrimary,
                                          fontWeight: isSelected
                                              ? FontWeight.w600
                                              : null,
                                        ),
                                      ),
                                    );
                                  },
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            );
          },
        );
      },
    );
  }

  void _saveDate() {
    if (_titleController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入标题')),
      );
      return;
    }

    final date = ImportantDate(
      id: widget.date?.id ?? '',
      title: _titleController.text.trim(),
      description: _descriptionController.text.trim().isNotEmpty
          ? _descriptionController.text.trim()
          : null,
      date: _selectedDate,
      dateType: _selectedType,
      calendarType: _calendarType,
      lunarMonth: _calendarType == CalendarType.lunar ? _lunarMonth : null,
      lunarDay: _calendarType == CalendarType.lunar ? _lunarDay : null,
      isRecurring: _isRecurring,
      reminderDays: _reminderDays,
      createdAt: widget.date?.createdAt ?? DateTime.now(),
      updatedAt: DateTime.now(),
    );

    if (_isEditing) {
      context.read<DatesBloc>().add(DateUpdated(date));
    } else {
      context.read<DatesBloc>().add(DateCreated(date));
    }
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

  String _getReminderLabel(int days) {
    if (days == 0) return '当天';
    if (days == 1) return '1天前';
    return '$days天前';
  }
}
