import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/shopping_item.dart';

/// 添加商品底部弹窗
class AddItemSheet extends StatefulWidget {
  final Function(String productName, ItemCategory? category, double quantity,
      String? unit, int priority, double? estimatedPrice, String? notes) onSubmit;
  final VoidCallback? onAIGenerate;

  const AddItemSheet({
    super.key,
    required this.onSubmit,
    this.onAIGenerate,
  });

  @override
  State<AddItemSheet> createState() => _AddItemSheetState();
}

class _AddItemSheetState extends State<AddItemSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _quantityController = TextEditingController(text: '1');
  final _unitController = TextEditingController();
  final _priceController = TextEditingController();
  final _notesController = TextEditingController();

  ItemCategory? _selectedCategory;
  int _priority = 3;

  @override
  void dispose() {
    _nameController.dispose();
    _quantityController.dispose();
    _unitController.dispose();
    _priceController.dispose();
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
                    _buildNameField(),
                    const SizedBox(height: 16),
                    _buildCategorySelector(),
                    const SizedBox(height: 16),
                    _buildQuantityAndUnit(),
                    const SizedBox(height: 16),
                    _buildPrioritySelector(),
                    const SizedBox(height: 16),
                    _buildPriceField(),
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
    return Container(
      margin: const EdgeInsets.only(top: 12),
      width: 40,
      height: 4,
      decoration: BoxDecoration(
        color: AppColors.divider,
        borderRadius: BorderRadius.circular(2),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text('添加商品', style: AppTextStyles.headline5),
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
      ),
    );
  }

  Widget _buildNameField() {
    return TextFormField(
      controller: _nameController,
      decoration: InputDecoration(
        labelText: '商品名称',
        hintText: '例如: 牛奶、鸡蛋、洗衣液',
        prefixIcon: const Icon(Icons.shopping_bag_outlined),
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
          return '请输入商品名称';
        }
        return null;
      },
      textInputAction: TextInputAction.next,
    );
  }

  Widget _buildCategorySelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('分类', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: ItemCategory.values.map((category) {
            final isSelected = _selectedCategory == category;
            return GestureDetector(
              onTap: () => setState(() => _selectedCategory = category),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: isSelected ? AppColors.primary : AppColors.chipBackground,
                  borderRadius: BorderRadius.circular(20),
                  border: isSelected ? null : Border.all(color: AppColors.divider),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(_getCategoryIcon(category), style: const TextStyle(fontSize: 14)),
                    const SizedBox(width: 4),
                    Text(
                      _getCategoryName(category),
                      style: AppTextStyles.caption.copyWith(
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

  Widget _buildQuantityAndUnit() {
    return Row(
      children: [
        Expanded(
          flex: 2,
          child: TextFormField(
            controller: _quantityController,
            decoration: InputDecoration(
              labelText: '数量',
              filled: true,
              fillColor: AppColors.inputBackground,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
            ),
            keyboardType: TextInputType.number,
            validator: (value) {
              if (value != null && value.isNotEmpty) {
                final num = double.tryParse(value);
                if (num == null || num <= 0) {
                  return '请输入有效数量';
                }
              }
              return null;
            },
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          flex: 3,
          child: TextFormField(
            controller: _unitController,
            decoration: InputDecoration(
              labelText: '单位',
              hintText: '件、盒、斤...',
              filled: true,
              fillColor: AppColors.inputBackground,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPrioritySelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('优先级', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        Row(
          children: [
            _buildPriorityOption(1, '紧急', AppColors.error),
            const SizedBox(width: 8),
            _buildPriorityOption(2, '优先', AppColors.warning),
            const SizedBox(width: 8),
            _buildPriorityOption(3, '普通', AppColors.textSecondary),
            const SizedBox(width: 8),
            _buildPriorityOption(4, '可选', AppColors.textTertiary),
          ],
        ),
      ],
    );
  }

  Widget _buildPriorityOption(int priority, String label, Color color) {
    final isSelected = _priority == priority;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _priority = priority),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: isSelected ? color : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isSelected ? color : AppColors.divider,
            ),
          ),
          child: Center(
            child: Text(
              label,
              style: AppTextStyles.caption.copyWith(
                color: isSelected ? Colors.white : color,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildPriceField() {
    return TextFormField(
      controller: _priceController,
      decoration: InputDecoration(
        labelText: '预估价格',
        hintText: '可选',
        prefixText: '¥ ',
        filled: true,
        fillColor: AppColors.inputBackground,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
      ),
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
    );
  }

  Widget _buildNotesField() {
    return TextFormField(
      controller: _notesController,
      decoration: InputDecoration(
        labelText: '备注',
        hintText: '品牌偏好、规格要求等',
        filled: true,
        fillColor: AppColors.inputBackground,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
      ),
      maxLines: 2,
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
            child: const Text('添加'),
          ),
        ),
      ],
    );
  }

  void _submit() {
    if (_formKey.currentState!.validate()) {
      final quantity = double.tryParse(_quantityController.text) ?? 1;
      final price = double.tryParse(_priceController.text);

      widget.onSubmit(
        _nameController.text.trim(),
        _selectedCategory,
        quantity,
        _unitController.text.trim().isEmpty ? null : _unitController.text.trim(),
        _priority,
        price,
        _notesController.text.trim().isEmpty ? null : _notesController.text.trim(),
      );
      Navigator.pop(context);
    }
  }

  String _getCategoryIcon(ItemCategory category) {
    switch (category) {
      case ItemCategory.dairy: return '🥛';
      case ItemCategory.meat: return '🥩';
      case ItemCategory.seafood: return '🐟';
      case ItemCategory.vegetable: return '🥬';
      case ItemCategory.fruit: return '🍎';
      case ItemCategory.grain: return '🍚';
      case ItemCategory.snack: return '🍪';
      case ItemCategory.beverage: return '🧃';
      case ItemCategory.household: return '🧹';
      case ItemCategory.personal: return '🧴';
      case ItemCategory.baby: return '🍼';
      case ItemCategory.pet: return '🐕';
      case ItemCategory.electronics: return '📱';
      case ItemCategory.clothing: return '👕';
      case ItemCategory.other: return '📦';
    }
  }

  String _getCategoryName(ItemCategory category) {
    switch (category) {
      case ItemCategory.dairy: return '乳制品';
      case ItemCategory.meat: return '肉类';
      case ItemCategory.seafood: return '海鲜';
      case ItemCategory.vegetable: return '蔬菜';
      case ItemCategory.fruit: return '水果';
      case ItemCategory.grain: return '粮油';
      case ItemCategory.snack: return '零食';
      case ItemCategory.beverage: return '饮料';
      case ItemCategory.household: return '家居';
      case ItemCategory.personal: return '个护';
      case ItemCategory.baby: return '母婴';
      case ItemCategory.pet: return '宠物';
      case ItemCategory.electronics: return '电子';
      case ItemCategory.clothing: return '服装';
      case ItemCategory.other: return '其他';
    }
  }
}

/// 显示添加商品弹窗
Future<void> showAddItemSheet(
  BuildContext context, {
  required Function(String productName, ItemCategory? category, double quantity,
      String? unit, int priority, double? estimatedPrice, String? notes) onSubmit,
  VoidCallback? onAIGenerate,
}) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      builder: (context, scrollController) => AddItemSheet(
        onSubmit: onSubmit,
        onAIGenerate: onAIGenerate,
      ),
    ),
  );
}
