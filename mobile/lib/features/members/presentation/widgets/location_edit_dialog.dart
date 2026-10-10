import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

class LocationEditResult {
  final String type;
  final String address;
  final bool isDelete;

  const LocationEditResult({
    required this.type,
    required this.address,
    this.isDelete = false,
  });

  static const delete = LocationEditResult(type: '', address: '', isDelete: true);
}

Future<LocationEditResult?> showLocationEditDialog({
  required BuildContext context,
  required String? existingType,
  required String? existingAddress,
  required Set<String> existingLocationTypes,
}) {
  return showDialog<LocationEditResult>(
    context: context,
    builder: (ctx) => _LocationEditDialog(
      existingType: existingType,
      existingAddress: existingAddress,
      existingLocationTypes: existingLocationTypes,
    ),
  );
}

class _LocationEditDialog extends StatefulWidget {
  final String? existingType;
  final String? existingAddress;
  final Set<String> existingLocationTypes;

  const _LocationEditDialog({
    required this.existingType,
    required this.existingAddress,
    required this.existingLocationTypes,
  });

  @override
  State<_LocationEditDialog> createState() => _LocationEditDialogState();
}

class _LocationEditDialogState extends State<_LocationEditDialog> {
  late final TextEditingController _addressController;
  late String _selectedType;
  final _formKey = GlobalKey<FormState>();

  bool get isEditing => widget.existingType != null;

  static const _locationTypes = {
    'home': '家庭住址',
    'work': '工作地址',
    'school': '学校地址',
    'other': '其他地址',
  };

  @override
  void initState() {
    super.initState();
    _addressController = TextEditingController(text: widget.existingAddress ?? '');
    _selectedType = widget.existingType ?? _firstAvailableType();
  }

  String _firstAvailableType() {
    for (final type in _locationTypes.keys) {
      if (!widget.existingLocationTypes.contains(type)) {
        return type;
      }
    }
    return 'other';
  }

  @override
  void dispose() {
    _addressController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(isEditing ? '编辑地址' : '添加地址', style: AppTextStyles.headline6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      content: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('地址类型', style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _locationTypes.entries.map((entry) {
                final isSelected = _selectedType == entry.key;
                final isOccupied = !isEditing &&
                    widget.existingLocationTypes.contains(entry.key) &&
                    entry.key != 'other';

                return ChoiceChip(
                  label: Text(entry.value),
                  selected: isSelected,
                  onSelected: isOccupied
                      ? null
                      : (selected) {
                          if (selected) setState(() => _selectedType = entry.key);
                        },
                  selectedColor: AppColors.primary.withValues(alpha: 0.15),
                  labelStyle: TextStyle(
                    color: isSelected
                        ? AppColors.primary
                        : isOccupied
                            ? AppColors.textTertiary
                            : AppColors.textPrimary,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                  ),
                  side: BorderSide(
                    color: isSelected ? AppColors.primary : AppColors.divider,
                  ),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                );
              }).toList(),
            ),
            const SizedBox(height: 16),
            Text('详细地址', style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary)),
            const SizedBox(height: 8),
            TextFormField(
              controller: _addressController,
              maxLines: 2,
              decoration: InputDecoration(
                hintText: '请输入详细地址',
                hintStyle: AppTextStyles.bodyText2.copyWith(color: AppColors.textTertiary),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.divider),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.divider),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.primary),
                ),
                contentPadding: const EdgeInsets.all(12),
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return '请输入地址';
                }
                return null;
              },
            ),
          ],
        ),
      ),
      actions: [
        if (isEditing)
          TextButton(
            onPressed: () => _confirmDelete(context),
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('删除'),
          ),
        const Spacer(),
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: _onSave,
          style: FilledButton.styleFrom(
            backgroundColor: AppColors.primary,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          ),
          child: const Text('保存'),
        ),
      ],
    );
  }

  void _onSave() {
    if (_formKey.currentState?.validate() != true) return;

    Navigator.of(context).pop(LocationEditResult(
      type: _selectedType,
      address: _addressController.text.trim(),
    ));
  }

  void _confirmDelete(BuildContext dialogContext) {
    showDialog(
      context: dialogContext,
      builder: (ctx) => AlertDialog(
        title: const Text('确认删除'),
        content: const Text('确定要删除此地址吗？'),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              Navigator.of(dialogContext).pop(LocationEditResult.delete);
            },
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }
}
