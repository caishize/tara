import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/shopping_list.dart';

/// 创建购物清单底部弹窗
class CreateListSheet extends StatefulWidget {
  final Function(String listName, ListType listType, DateTime? dueDate) onSubmit;
  final VoidCallback? onAIGenerate;

  const CreateListSheet({
    super.key,
    required this.onSubmit,
    this.onAIGenerate,
  });

  @override
  State<CreateListSheet> createState() => _CreateListSheetState();
}

class _CreateListSheetState extends State<CreateListSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();

  ListType _selectedType = ListType.regular;
  DateTime? _dueDate;

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Padding(
        padding: EdgeInsets.only(
          left: 20,
          right: 20,
          top: 12,
          bottom: MediaQuery.of(context).viewInsets.bottom + 20,
        ),
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHandle(),
              const SizedBox(height: 8),
              _buildHeader(),
              const SizedBox(height: 20),
              _buildNameField(),
              const SizedBox(height: 20),
              _buildTypeSelector(),
              const SizedBox(height: 20),
              _buildDueDatePicker(),
              const SizedBox(height: 24),
              _buildQuickTemplates(),
              const SizedBox(height: 24),
              _buildActions(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHandle() {
    return Center(
      child: Container(
        width: 40,
        height: 4,
        decoration: BoxDecoration(
          color: AppColors.divider,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text('创建购物清单', style: AppTextStyles.headline5),
        if (widget.onAIGenerate != null)
          TextButton.icon(
            onPressed: widget.onAIGenerate,
            icon: const Icon(Icons.auto_awesome, size: 18),
            label: const Text('AI生成'),
            style: TextButton.styleFrom(
              foregroundColor: AppColors.accent3,
            ),
          ),
      ],
    );
  }

  Widget _buildNameField() {
    return TextFormField(
      controller: _nameController,
      decoration: InputDecoration(
        labelText: '清单名称',
        hintText: '例如: 周末采购、生日派对准备',
        prefixIcon: const Icon(Icons.edit_outlined),
        filled: true,
        fillColor: AppColors.inputBackground,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.primary, width: 2),
        ),
      ),
      validator: (value) {
        if (value == null || value.trim().isEmpty) {
          return '请输入清单名称';
        }
        return null;
      },
      textInputAction: TextInputAction.done,
    );
  }

  Widget _buildTypeSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('清单类型', style: AppTextStyles.subtitle2),
        const SizedBox(height: 12),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: ListType.values.map((type) {
            final isSelected = _selectedType == type;
            return GestureDetector(
              onTap: () => setState(() => _selectedType = type),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: isSelected ? _getTypeColor(type) : Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isSelected ? _getTypeColor(type) : AppColors.divider,
                    width: isSelected ? 2 : 1,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _getTypeIcon(type),
                      style: const TextStyle(fontSize: 18),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _getTypeName(type),
                      style: AppTextStyles.subtitle2.copyWith(
                        color: isSelected ? Colors.white : AppColors.textSecondary,
                        fontWeight: isSelected ? FontWeight.w600 : null,
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

  Widget _buildDueDatePicker() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('截止日期', style: AppTextStyles.subtitle2),
        const SizedBox(height: 12),
        GestureDetector(
          onTap: _selectDueDate,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              color: AppColors.inputBackground,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.calendar_today_outlined,
                  size: 20,
                  color: _dueDate != null ? AppColors.primary : AppColors.textTertiary,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _dueDate != null
                        ? '${_dueDate!.year}/${_dueDate!.month}/${_dueDate!.day}'
                        : '选择截止日期（可选）',
                    style: AppTextStyles.bodyText2.copyWith(
                      color: _dueDate != null ? AppColors.textPrimary : AppColors.textTertiary,
                    ),
                  ),
                ),
                if (_dueDate != null)
                  GestureDetector(
                    onTap: () => setState(() => _dueDate = null),
                    child: const Icon(
                      Icons.close,
                      size: 18,
                      color: AppColors.textTertiary,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildQuickTemplates() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('快速模板', style: AppTextStyles.subtitle2),
        const SizedBox(height: 12),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              _buildTemplateChip('🎂', '生日派对', ListType.regular),
              _buildTemplateChip('🏠', '日常补货', ListType.replenishment),
              _buildTemplateChip('📚', '新学期准备', ListType.seasonal),
              _buildTemplateChip('🎄', '节日采购', ListType.seasonal),
              _buildTemplateChip('🏕️', '露营装备', ListType.regular),
              _buildTemplateChip('🧹', '大扫除用品', ListType.bulk),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildTemplateChip(String icon, String name, ListType type) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ActionChip(
        avatar: Text(icon, style: const TextStyle(fontSize: 16)),
        label: Text(name),
        onPressed: () {
          setState(() {
            _nameController.text = name;
            _selectedType = type;
          });
        },
        backgroundColor: AppColors.chipBackground,
        side: BorderSide.none,
        labelStyle: AppTextStyles.caption.copyWith(
          color: AppColors.textSecondary,
        ),
      ),
    );
  }

  Widget _buildActions() {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton(
            onPressed: () => Navigator.pop(context),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              side: const BorderSide(color: AppColors.divider),
            ),
            child: const Text('取消'),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          flex: 2,
          child: ElevatedButton(
            onPressed: _submit,
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              elevation: 0,
            ),
            child: const Text('创建'),
          ),
        ),
      ],
    );
  }

  Future<void> _selectDueDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _dueDate ?? DateTime.now().add(const Duration(days: 7)),
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365)),
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
    if (date != null) {
      setState(() => _dueDate = date);
    }
  }

  void _submit() {
    if (_formKey.currentState!.validate()) {
      widget.onSubmit(
        _nameController.text.trim(),
        _selectedType,
        _dueDate,
      );
      Navigator.pop(context);
    }
  }

  Color _getTypeColor(ListType type) {
    switch (type) {
      case ListType.regular:
        return AppColors.primary;
      case ListType.replenishment:
        return AppColors.secondary;
      case ListType.seasonal:
        return AppColors.accent1;
      case ListType.bulk:
        return AppColors.accent3;
      case ListType.urgent:
        return AppColors.error;
    }
  }

  String _getTypeIcon(ListType type) {
    switch (type) {
      case ListType.regular:
        return '📋';
      case ListType.replenishment:
        return '🔄';
      case ListType.seasonal:
        return '🗓️';
      case ListType.bulk:
        return '📦';
      case ListType.urgent:
        return '🚨';
    }
  }

  String _getTypeName(ListType type) {
    switch (type) {
      case ListType.regular:
        return '常规采购';
      case ListType.replenishment:
        return '日常补货';
      case ListType.seasonal:
        return '季节性';
      case ListType.bulk:
        return '批量采购';
      case ListType.urgent:
        return '紧急采购';
    }
  }
}

/// 显示创建清单弹窗
Future<void> showCreateListSheet(
  BuildContext context, {
  required Function(String listName, ListType listType, DateTime? dueDate) onSubmit,
  VoidCallback? onAIGenerate,
}) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => CreateListSheet(
      onSubmit: onSubmit,
      onAIGenerate: onAIGenerate,
    ),
  );
}
