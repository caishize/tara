import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../bloc/goals_bloc.dart';

class AddGoalSheet extends StatefulWidget {
  final String memberId;

  const AddGoalSheet({super.key, required this.memberId});

  @override
  State<AddGoalSheet> createState() => _AddGoalSheetState();
}

class _AddGoalSheetState extends State<AddGoalSheet> {
  final _formKey = GlobalKey<FormState>();
  final _descriptionController = TextEditingController();
  final _targetController = TextEditingController();
  final _unitController = TextEditingController();

  String _selectedType = 'reading';
  DateTime _startDate = DateTime.now();
  DateTime _endDate = DateTime.now().add(const Duration(days: 30));

  final List<Map<String, dynamic>> _goalTypes = [
    {'type': 'reading', 'name': '阅读', 'icon': Icons.menu_book, 'unit': '本'},
    {'type': 'exercise', 'name': '运动', 'icon': Icons.fitness_center, 'unit': '次'},
    {'type': 'savings', 'name': '储蓄', 'icon': Icons.savings, 'unit': '元'},
    {'type': 'learning', 'name': '学习', 'icon': Icons.school, 'unit': '小时'},
    {'type': 'weight', 'name': '体重', 'icon': Icons.monitor_weight, 'unit': 'kg'},
    {'type': 'sleep', 'name': '睡眠', 'icon': Icons.bedtime, 'unit': '小时'},
    {'type': 'meditation', 'name': '冥想', 'icon': Icons.self_improvement, 'unit': '分钟'},
    {'type': 'work', 'name': '工作', 'icon': Icons.work, 'unit': '项'},
  ];

  @override
  void initState() {
    super.initState();
    _unitController.text = '本';
  }

  @override
  void dispose() {
    _descriptionController.dispose();
    _targetController.dispose();
    _unitController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      child: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Handle bar
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: AppColors.textSecondary.withValues(alpha: 0.3),
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Title
                Text('创建新目标', style: AppTextStyles.headline6),
                const SizedBox(height: 20),

                // Goal type selection
                Text('目标类型', style: AppTextStyles.subtitle2),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _goalTypes.map((type) {
                    final isSelected = _selectedType == type['type'];
                    return ChoiceChip(
                      avatar: Icon(
                        type['icon'] as IconData,
                        size: 18,
                        color: isSelected ? AppColors.primary : AppColors.textSecondary,
                      ),
                      label: Text(type['name'] as String),
                      selected: isSelected,
                      onSelected: (selected) {
                        if (selected) {
                          setState(() {
                            _selectedType = type['type'] as String;
                            _unitController.text = type['unit'] as String;
                          });
                        }
                      },
                      selectedColor: AppColors.primary.withValues(alpha: 0.2),
                    );
                  }).toList(),
                ),
                const SizedBox(height: 20),

                // Description
                TextFormField(
                  controller: _descriptionController,
                  decoration: const InputDecoration(
                    labelText: '目标描述 *',
                    hintText: '例如: 每月阅读4本书',
                    prefixIcon: Icon(Icons.description),
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return '请输入目标描述';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),

                // Target value and unit
                Row(
                  children: [
                    Expanded(
                      flex: 2,
                      child: TextFormField(
                        controller: _targetController,
                        decoration: const InputDecoration(
                          labelText: '目标值 *',
                          hintText: '例如: 12',
                          prefixIcon: Icon(Icons.flag),
                        ),
                        keyboardType: TextInputType.number,
                        validator: (value) {
                          if (value == null || value.trim().isEmpty) {
                            return '请输入目标值';
                          }
                          if (double.tryParse(value) == null) {
                            return '请输入有效数字';
                          }
                          return null;
                        },
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: TextFormField(
                        controller: _unitController,
                        decoration: const InputDecoration(
                          labelText: '单位',
                          hintText: '本',
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Date range
                Row(
                  children: [
                    Expanded(
                      child: InkWell(
                        onTap: () => _selectStartDate(context),
                        child: InputDecorator(
                          decoration: const InputDecoration(
                            labelText: '开始日期',
                            prefixIcon: Icon(Icons.calendar_today),
                          ),
                          child: Text(
                            '${_startDate.year}-${_startDate.month.toString().padLeft(2, '0')}-${_startDate.day.toString().padLeft(2, '0')}',
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: InkWell(
                        onTap: () => _selectEndDate(context),
                        child: InputDecorator(
                          decoration: const InputDecoration(
                            labelText: '结束日期',
                            prefixIcon: Icon(Icons.event),
                          ),
                          child: Text(
                            '${_endDate.year}-${_endDate.month.toString().padLeft(2, '0')}-${_endDate.day.toString().padLeft(2, '0')}',
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),

                // Submit button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _submit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text('创建目标'),
                  ),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _selectStartDate(BuildContext context) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _startDate,
      firstDate: DateTime.now().subtract(const Duration(days: 30)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null) {
      setState(() {
        _startDate = picked;
        if (_endDate.isBefore(_startDate)) {
          _endDate = _startDate.add(const Duration(days: 30));
        }
      });
    }
  }

  Future<void> _selectEndDate(BuildContext context) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _endDate,
      firstDate: _startDate.add(const Duration(days: 1)),
      lastDate: _startDate.add(const Duration(days: 365 * 2)),
    );
    if (picked != null) {
      setState(() => _endDate = picked);
    }
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;

    final targetValue = double.tryParse(_targetController.text.trim());
    if (targetValue == null || targetValue <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入有效的目标值')),
      );
      return;
    }

    context.read<GoalsBloc>().add(GoalCreateRequested(
      memberId: widget.memberId,
      goalType: _selectedType,
      description: _descriptionController.text.trim(),
      targetValue: targetValue,
      unit: _unitController.text.trim().isNotEmpty ? _unitController.text.trim() : '次',
      startDate: _startDate,
      endDate: _endDate,
    ));

    Navigator.of(context).pop();
  }
}
