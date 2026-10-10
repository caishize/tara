import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';

/// 添加日程事件底部弹窗
class AddEventSheet extends StatefulWidget {
  final Function(
    String title,
    DateTime startTime,
    DateTime? endTime,
    String eventType,
    String? location,
    String priority,
    String? notes,
  ) onSubmit;

  const AddEventSheet({
    super.key,
    required this.onSubmit,
  });

  @override
  State<AddEventSheet> createState() => _AddEventSheetState();
}

class _AddEventSheetState extends State<AddEventSheet> {
  final _formKey = GlobalKey<FormState>();
  final _titleController = TextEditingController();
  final _locationController = TextEditingController();
  final _notesController = TextEditingController();

  DateTime _startDate = DateTime.now().add(const Duration(hours: 1));
  DateTime? _endDate;
  String _eventType = 'other';
  String _priority = 'normal';

  static const _eventTypes = [
    ('meeting', '会议'),
    ('appointment', '约会'),
    ('reminder', '提醒'),
    ('birthday', '生日'),
    ('anniversary', '纪念日'),
    ('other', '其他'),
  ];

  static const _priorities = [
    ('low', '低'),
    ('normal', '普通'),
    ('high', '高'),
    ('critical', '紧急'),
  ];

  @override
  void dispose() {
    _titleController.dispose();
    _locationController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildHandle(),
          _buildHeader(),
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildTitleField(),
                    const SizedBox(height: 16),
                    _buildEventTypeSelector(),
                    const SizedBox(height: 16),
                    _buildDateTimePicker('开始时间', _startDate, (dt) {
                      setState(() => _startDate = dt);
                    }),
                    const SizedBox(height: 16),
                    _buildOptionalEndTime(),
                    const SizedBox(height: 16),
                    _buildLocationField(),
                    const SizedBox(height: 16),
                    _buildPrioritySelector(),
                    const SizedBox(height: 16),
                    _buildNotesField(),
                    const SizedBox(height: 24),
                    _buildActions(),
                    SizedBox(height: MediaQuery.of(context).viewInsets.bottom),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHandle() {
    return Center(
      child: Container(
        margin: const EdgeInsets.only(top: 12),
        width: 40,
        height: 4,
        decoration: BoxDecoration(
          color: Colors.grey[300],
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Text(
            '添加日程',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close, color: AppColors.textSecondary),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }

  Widget _buildTitleField() {
    return TextFormField(
      controller: _titleController,
      decoration: InputDecoration(
        labelText: '事件标题',
        hintText: '如：团队周会、看牙医',
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        prefixIcon: const Icon(Icons.event_note),
      ),
      validator: (value) {
        if (value == null || value.trim().isEmpty) {
          return '请输入事件标题';
        }
        return null;
      },
    );
  }

  Widget _buildEventTypeSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('事件类型',
            style: TextStyle(fontSize: 14, color: AppColors.textSecondary)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _eventTypes.map((type) {
            final isSelected = _eventType == type.$1;
            return ChoiceChip(
              label: Text(type.$2),
              selected: isSelected,
              onSelected: (_) => setState(() => _eventType = type.$1),
              selectedColor: AppColors.primary.withOpacity(0.2),
              labelStyle: TextStyle(
                color: isSelected ? AppColors.primary : AppColors.textSecondary,
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildDateTimePicker(
    String label,
    DateTime dateTime,
    ValueChanged<DateTime> onChanged,
  ) {
    return InkWell(
      onTap: () async {
        final date = await showDatePicker(
          context: context,
          initialDate: dateTime,
          firstDate: DateTime.now().subtract(const Duration(days: 365)),
          lastDate: DateTime.now().add(const Duration(days: 730)),
        );
        if (date == null || !mounted) return;

        final time = await showTimePicker(
          context: context,
          initialTime: TimeOfDay.fromDateTime(dateTime),
        );
        if (time == null || !mounted) return;

        onChanged(DateTime(
          date.year, date.month, date.day, time.hour, time.minute,
        ));
      },
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          prefixIcon: const Icon(Icons.access_time),
        ),
        child: Text(
          _formatDateTime(dateTime),
          style: const TextStyle(fontSize: 16),
        ),
      ),
    );
  }

  Widget _buildOptionalEndTime() {
    if (_endDate != null) {
      return Row(
        children: [
          Expanded(
            child: _buildDateTimePicker('结束时间', _endDate!, (dt) {
              setState(() => _endDate = dt);
            }),
          ),
          IconButton(
            icon: const Icon(Icons.close, size: 20),
            onPressed: () => setState(() => _endDate = null),
          ),
        ],
      );
    }
    return OutlinedButton.icon(
      onPressed: () {
        setState(() {
          _endDate = _startDate.add(const Duration(hours: 1));
        });
      },
      icon: const Icon(Icons.add, size: 18),
      label: const Text('添加结束时间'),
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.textSecondary,
        side: BorderSide(color: Colors.grey[300]!),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  Widget _buildLocationField() {
    return TextFormField(
      controller: _locationController,
      decoration: InputDecoration(
        labelText: '地点 (可选)',
        hintText: '如：会议室A、医院',
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        prefixIcon: const Icon(Icons.location_on_outlined),
      ),
    );
  }

  Widget _buildPrioritySelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('优先级',
            style: TextStyle(fontSize: 14, color: AppColors.textSecondary)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: _priorities.map((p) {
            final isSelected = _priority == p.$1;
            return ChoiceChip(
              label: Text(p.$2),
              selected: isSelected,
              onSelected: (_) => setState(() => _priority = p.$1),
              selectedColor: AppColors.primary.withOpacity(0.2),
              labelStyle: TextStyle(
                color: isSelected ? AppColors.primary : AppColors.textSecondary,
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildNotesField() {
    return TextFormField(
      controller: _notesController,
      decoration: InputDecoration(
        labelText: '备注 (可选)',
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        prefixIcon: const Icon(Icons.notes),
      ),
      maxLines: 3,
    );
  }

  Widget _buildActions() {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: _onSubmit,
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: const Text(
          '创建日程',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }

  void _onSubmit() {
    if (_formKey.currentState?.validate() != true) return;

    widget.onSubmit(
      _titleController.text.trim(),
      _startDate,
      _endDate,
      _eventType,
      _locationController.text.trim().isEmpty
          ? null
          : _locationController.text.trim(),
      _priority,
      _notesController.text.trim().isEmpty
          ? null
          : _notesController.text.trim(),
    );
    Navigator.of(context).pop();
  }

  String _formatDateTime(DateTime dt) {
    final month = dt.month.toString().padLeft(2, '0');
    final day = dt.day.toString().padLeft(2, '0');
    final hour = dt.hour.toString().padLeft(2, '0');
    final minute = dt.minute.toString().padLeft(2, '0');
    return '${dt.year}-$month-$day $hour:$minute';
  }
}
