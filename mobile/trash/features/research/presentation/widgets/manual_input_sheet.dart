import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

class ManualInputSheet extends StatefulWidget {
  final String type; // 'note' or 'url'
  final void Function(String content) onSubmit;

  const ManualInputSheet({
    super.key,
    required this.type,
    required this.onSubmit,
  });

  @override
  State<ManualInputSheet> createState() => _ManualInputSheetState();
}

class _ManualInputSheetState extends State<ManualInputSheet> {
  late TextEditingController _controller;
  bool _isValid = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
    _controller.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    final text = _controller.text.trim();
    setState(() {
      if (widget.type == 'url') {
        _isValid = text.isNotEmpty &&
            (text.startsWith('http://') || text.startsWith('https://'));
      } else {
        _isValid = text.isNotEmpty;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final isNote = widget.type == 'note';

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Handle
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppColors.divider,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              // Title
              Row(
                children: [
                  Icon(
                    isNote ? Icons.note_add : Icons.link,
                    color: AppColors.primary,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    isNote ? '添加笔记' : '添加链接',
                    style: AppTextStyles.headline6,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              // Description
              Text(
                isNote
                    ? '添加您自己的想法、备注或补充信息'
                    : '粘贴网页链接，系统将自动提取内容',
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 16),
              // Input field
              TextField(
                controller: _controller,
                maxLines: isNote ? 5 : 1,
                keyboardType: isNote ? TextInputType.multiline : TextInputType.url,
                autofocus: true,
                decoration: InputDecoration(
                  hintText: isNote ? '输入您的笔记...' : 'https://',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: AppColors.divider),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: AppColors.primary, width: 2),
                  ),
                  filled: true,
                  fillColor: AppColors.background,
                ),
              ),
              if (widget.type == 'url' && _controller.text.isNotEmpty && !_isValid)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    '请输入有效的网址 (以 http:// 或 https:// 开头)',
                    style: AppTextStyles.caption.copyWith(
                      color: Colors.red,
                    ),
                  ),
                ),
              const SizedBox(height: 20),
              // Submit button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _isValid
                      ? () => widget.onSubmit(_controller.text.trim())
                      : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: Text(
                    '添加',
                    style: AppTextStyles.button.copyWith(color: Colors.white),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
