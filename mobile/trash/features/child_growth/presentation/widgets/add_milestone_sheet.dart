import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/milestone.dart';
import '../bloc/child_growth_bloc.dart';

class AddMilestoneSheet extends StatefulWidget {
  final String childId;
  final String childName;

  const AddMilestoneSheet({
    super.key,
    required this.childId,
    required this.childName,
  });

  @override
  State<AddMilestoneSheet> createState() => _AddMilestoneSheetState();
}

class _AddMilestoneSheetState extends State<AddMilestoneSheet> {
  final _titleController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _notesController = TextEditingController();
  MilestoneType _selectedType = MilestoneType.physical;
  MilestoneTemplate? _selectedTemplate;
  DateTime _achievedDate = DateTime.now();

  @override
  void dispose() {
    _titleController.dispose();
    _descriptionController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.9,
      ),
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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildTypeSelector(),
                  const SizedBox(height: 20),
                  _buildTemplateSelector(),
                  const SizedBox(height: 20),
                  _buildTitleField(),
                  const SizedBox(height: 20),
                  _buildDateSelector(),
                  const SizedBox(height: 20),
                  _buildDescriptionField(),
                  const SizedBox(height: 20),
                  _buildNotesField(),
                  const SizedBox(height: 32),
                  _buildSubmitButton(),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHandle() {
    return GestureDetector(
      onTap: () => Navigator.pop(context),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Center(
          child: Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: AppColors.divider,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Color(_selectedType.typeColorValue),
                  Color(_selectedType.typeColorValue).withValues(alpha: 0.7),
                ],
              ),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.emoji_events, color: Colors.white),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('记录里程碑', style: AppTextStyles.headline5),
                const SizedBox(height: 2),
                Text(
                  '记录 ${widget.childName} 的成长时刻',
                  style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
                ),
              ],
            ),
          ),
          GestureDetector(
            onTap: () => Navigator.pop(context),
            child: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.close,
                color: AppColors.textSecondary,
                size: 20,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTypeSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('里程碑类型', style: AppTextStyles.subtitle1),
        const SizedBox(height: 12),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: MilestoneType.values.map((type) {
            final isSelected = _selectedType == type;
            final color = Color(_getTypeColorValue(type));
            return GestureDetector(
              onTap: () {
                setState(() {
                  _selectedType = type;
                  _selectedTemplate = null;
                });
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  color: isSelected ? color : Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected ? color : AppColors.divider,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _getTypeIcon(type),
                      style: const TextStyle(fontSize: 16),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      _getTypeName(type),
                      style: AppTextStyles.bodyText2.copyWith(
                        color: isSelected ? Colors.white : AppColors.textPrimary,
                        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildTemplateSelector() {
    final templates = MilestoneTemplate.getByType(_selectedType);
    if (templates.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('常见里程碑', style: AppTextStyles.subtitle1),
            const SizedBox(width: 8),
            Text(
              '(可选)',
              style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: templates.map((template) {
            final isSelected = _selectedTemplate == template;
            return GestureDetector(
              onTap: () {
                setState(() {
                  _selectedTemplate = template;
                  _titleController.text = template.title;
                  _descriptionController.text = template.description;
                });
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: isSelected ? AppColors.primary.withValues(alpha: 0.1) : AppColors.inputBackground,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: isSelected ? AppColors.primary : Colors.transparent,
                  ),
                ),
                child: Text(
                  template.title,
                  style: AppTextStyles.caption.copyWith(
                    color: isSelected ? AppColors.primary : AppColors.textPrimary,
                    fontWeight: isSelected ? FontWeight.w500 : FontWeight.normal,
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildTitleField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('里程碑名称', style: AppTextStyles.subtitle1),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            color: AppColors.inputBackground,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.divider),
          ),
          child: TextField(
            controller: _titleController,
            decoration: InputDecoration(
              hintText: '如: 第一次独立行走',
              hintStyle: AppTextStyles.bodyText2.copyWith(
                color: AppColors.textTertiary,
              ),
              border: InputBorder.none,
              contentPadding: const EdgeInsets.all(16),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDateSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('达成日期', style: AppTextStyles.subtitle1),
        const SizedBox(height: 12),
        GestureDetector(
          onTap: _selectDate,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.inputBackground,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.divider),
            ),
            child: Row(
              children: [
                Icon(Icons.calendar_today, color: Color(_selectedType.typeColorValue)),
                const SizedBox(width: 12),
                Text(
                  _formatDate(_achievedDate),
                  style: AppTextStyles.bodyText1,
                ),
                const Spacer(),
                const Icon(Icons.chevron_right, color: AppColors.textTertiary),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDescriptionField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('详细描述', style: AppTextStyles.subtitle1),
            const SizedBox(width: 8),
            Text(
              '(可选)',
              style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            color: AppColors.inputBackground,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.divider),
          ),
          child: TextField(
            controller: _descriptionController,
            maxLines: 2,
            decoration: InputDecoration(
              hintText: '描述这个成长时刻...',
              hintStyle: AppTextStyles.bodyText2.copyWith(
                color: AppColors.textTertiary,
              ),
              border: InputBorder.none,
              contentPadding: const EdgeInsets.all(16),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildNotesField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('妈妈的话', style: AppTextStyles.subtitle1),
            const SizedBox(width: 8),
            Text(
              '(可选)',
              style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            color: AppColors.inputBackground,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.divider),
          ),
          child: TextField(
            controller: _notesController,
            maxLines: 2,
            decoration: InputDecoration(
              hintText: '给宝宝写点什么吧...',
              hintStyle: AppTextStyles.bodyText2.copyWith(
                color: AppColors.textTertiary,
              ),
              border: InputBorder.none,
              contentPadding: const EdgeInsets.all(16),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSubmitButton() {
    return BlocBuilder<ChildGrowthBloc, ChildGrowthState>(
      builder: (context, state) {
        final isLoading = state is ChildGrowthLoaded && state.isAddingRecord;

        return SizedBox(
          width: double.infinity,
          height: 52,
          child: ElevatedButton(
            onPressed: isLoading ? null : _submit,
            style: ElevatedButton.styleFrom(
              backgroundColor: Color(_selectedType.typeColorValue),
              disabledBackgroundColor: AppColors.divider,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              elevation: 4,
              shadowColor: Color(_selectedType.typeColorValue).withValues(alpha: 0.3),
            ),
            child: isLoading
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                    ),
                  )
                : Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.celebration, color: Colors.white, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        '记录这个时刻',
                        style: AppTextStyles.subtitle1.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
          ),
        );
      },
    );
  }

  Future<void> _selectDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _achievedDate,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
      locale: const Locale('zh', 'CN'),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: ColorScheme.light(
              primary: Color(_selectedType.typeColorValue),
              onPrimary: Colors.white,
              surface: Colors.white,
              onSurface: AppColors.textPrimary,
            ),
          ),
          child: child!,
        );
      },
    );
    if (picked != null) {
      setState(() => _achievedDate = picked);
    }
  }

  void _submit() {
    final title = _titleController.text.trim();
    if (title.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('请输入里程碑名称'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    context.read<ChildGrowthBloc>().add(
      MilestoneAddRequested(
        childId: widget.childId,
        type: _selectedType,
        title: title,
        achievedDate: _achievedDate,
        description: _descriptionController.text.isEmpty ? null : _descriptionController.text,
        notes: _notesController.text.isEmpty ? null : _notesController.text,
      ),
    );

    Navigator.pop(context);
  }

  String _getTypeName(MilestoneType type) {
    switch (type) {
      case MilestoneType.physical:
        return '运动发育';
      case MilestoneType.cognitive:
        return '认知发育';
      case MilestoneType.language:
        return '语言发育';
      case MilestoneType.social:
        return '社交发育';
      case MilestoneType.emotional:
        return '情感发育';
    }
  }

  String _getTypeIcon(MilestoneType type) {
    switch (type) {
      case MilestoneType.physical:
        return '🏃';
      case MilestoneType.cognitive:
        return '🧠';
      case MilestoneType.language:
        return '🗣️';
      case MilestoneType.social:
        return '👋';
      case MilestoneType.emotional:
        return '💕';
    }
  }

  int _getTypeColorValue(MilestoneType type) {
    switch (type) {
      case MilestoneType.physical:
        return 0xFF4CAF50;
      case MilestoneType.cognitive:
        return 0xFF2196F3;
      case MilestoneType.language:
        return 0xFFFF9800;
      case MilestoneType.social:
        return 0xFF9C27B0;
      case MilestoneType.emotional:
        return 0xFFE91E63;
    }
  }

  String _formatDate(DateTime date) {
    return '${date.year}年${date.month}月${date.day}日';
  }
}

extension _MilestoneTypeExt on MilestoneType {
  int get typeColorValue {
    switch (this) {
      case MilestoneType.physical:
        return 0xFF4CAF50;
      case MilestoneType.cognitive:
        return 0xFF2196F3;
      case MilestoneType.language:
        return 0xFFFF9800;
      case MilestoneType.social:
        return 0xFF9C27B0;
      case MilestoneType.emotional:
        return 0xFFE91E63;
    }
  }
}
