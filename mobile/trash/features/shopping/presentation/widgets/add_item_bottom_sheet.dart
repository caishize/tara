import 'package:flutter/material.dart';
import '../../domain/entities/shopping_item.dart';
import 'item_tag_selector.dart';
import 'assignee_selector.dart';

/// 添加购物商品底部弹窗
/// 匹配原型设计中间面板
class AddItemBottomSheet extends StatefulWidget {
  final void Function(
    String productName,
    String? notes,
    List<ItemTag> tags,
    String? assignedTo,
  ) onSubmit;
  final List<FamilyMemberInfo> familyMembers;
  final String currentUserId;

  const AddItemBottomSheet({
    super.key,
    required this.onSubmit,
    required this.familyMembers,
    required this.currentUserId,
  });

  @override
  State<AddItemBottomSheet> createState() => _AddItemBottomSheetState();
}

class _AddItemBottomSheetState extends State<AddItemBottomSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _notesController = TextEditingController();
  List<ItemTag> _selectedTags = [];
  String? _selectedAssigneeId;

  @override
  void dispose() {
    _nameController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bottomPadding = MediaQuery.of(context).viewInsets.bottom;

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildHandle(),
          // 顶部图片占位区域（匹配原型图）
          _buildImagePlaceholder(),
          _buildHeader(context),
          Flexible(
            child: SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + bottomPadding),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 物品名称
                    _buildNameField(),
                    const SizedBox(height: 16),
                    // 备注说明
                    _buildNotesField(),
                    const SizedBox(height: 20),
                    // 标签分类
                    ItemTagSelector(
                      selectedTags: _selectedTags,
                      onTagsChanged: (tags) => setState(() => _selectedTags = tags),
                    ),
                    const SizedBox(height: 20),
                    // 指定购买人
                    AssigneeSelector(
                      selectedAssigneeId: _selectedAssigneeId,
                      onAssigneeChanged: (id) => setState(() => _selectedAssigneeId = id),
                      familyMembers: widget.familyMembers,
                      currentUserId: widget.currentUserId,
                    ),
                    const SizedBox(height: 24),
                    // 提交按钮
                    _buildSubmitButton(context),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// 顶部图片占位区域（匹配原型图设计）
  Widget _buildImagePlaceholder() {
    return Container(
      height: 120,
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(20, 8, 20, 0),
      decoration: BoxDecoration(
        color: Colors.grey.shade200,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Center(
        child: Icon(
          Icons.add_photo_alternate_outlined,
          size: 36,
          color: Colors.grey.shade400,
        ),
      ),
    );
  }

  Widget _buildHandle() {
    return Container(
      margin: const EdgeInsets.only(top: 12),
      width: 40,
      height: 4,
      decoration: BoxDecoration(
        color: Colors.grey.shade300,
        borderRadius: BorderRadius.circular(2),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '添加购物项',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }

  Widget _buildNameField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '物品名称',
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w500,
              ),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: _nameController,
          decoration: InputDecoration(
            hintText: '请输入物品名称',
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: Colors.grey.shade300),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: Colors.grey.shade300),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: Theme.of(context).primaryColor, width: 2),
            ),
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          ),
          validator: (value) {
            if (value == null || value.trim().isEmpty) {
              return '请输入物品名称';
            }
            return null;
          },
        ),
      ],
    );
  }

  Widget _buildNotesField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '备注说明',
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w500,
              ),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: _notesController,
          maxLines: 3,
          decoration: InputDecoration(
            hintText: '添加购买说明或链接...',
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: Colors.grey.shade300),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: Colors.grey.shade300),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: Theme.of(context).primaryColor, width: 2),
            ),
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          ),
        ),
      ],
    );
  }

  Widget _buildSubmitButton(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton.icon(
        onPressed: _handleSubmit,
        icon: const Icon(Icons.add),
        label: const Text('添加到清单'),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF4CAF50),
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  void _handleSubmit() {
    if (_formKey.currentState?.validate() ?? false) {
      widget.onSubmit(
        _nameController.text.trim(),
        _notesController.text.trim().isEmpty ? null : _notesController.text.trim(),
        _selectedTags,
        _selectedAssigneeId,
      );
      Navigator.of(context).pop();
    }
  }
}

/// 显示添加商品底部弹窗
Future<void> showAddItemBottomSheet(
  BuildContext context, {
  required void Function(String productName, String? notes, List<ItemTag> tags, String? assignedTo)
      onSubmit,
  required List<FamilyMemberInfo> familyMembers,
  required String currentUserId,
}) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      builder: (context, scrollController) => AddItemBottomSheet(
        onSubmit: onSubmit,
        familyMembers: familyMembers,
        currentUserId: currentUserId,
      ),
    ),
  );
}
