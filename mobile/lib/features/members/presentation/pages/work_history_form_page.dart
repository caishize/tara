import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:get_it/get_it.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/app_button.dart';
import '../../../../shared/widgets/app_text_field.dart';
import '../../data/datasources/member_remote_datasource.dart';
import '../../data/models/work_history_model.dart';

class WorkHistoryFormPage extends StatefulWidget {
  final String memberId;
  final String? workHistoryId;

  const WorkHistoryFormPage({
    super.key,
    required this.memberId,
    this.workHistoryId,
  });

  @override
  State<WorkHistoryFormPage> createState() => _WorkHistoryFormPageState();
}

class _WorkHistoryFormPageState extends State<WorkHistoryFormPage> {
  final _formKey = GlobalKey<FormState>();
  final _companyController = TextEditingController();
  final _positionController = TextEditingController();
  final _departmentController = TextEditingController();
  final _notesController = TextEditingController();

  late final MemberRemoteDataSource _dataSource;
  DateTime? _startDate;
  DateTime? _endDate;
  bool _isCurrent = false;
  bool _isLoading = false;
  bool _isDeleting = false;
  WorkHistoryModel? _existingWorkHistory;

  bool get isEditing => widget.workHistoryId != null;

  @override
  void initState() {
    super.initState();
    _dataSource = GetIt.instance<MemberRemoteDataSource>();
    if (isEditing) {
      _loadExistingData();
    }
  }

  Future<void> _loadExistingData() async {
    setState(() => _isLoading = true);
    try {
      final list = await _dataSource.getWorkHistory(widget.memberId);
      final existing = list.where((wh) => wh.id == widget.workHistoryId).firstOrNull;
      if (existing != null) {
        _existingWorkHistory = existing;
        _companyController.text = existing.companyName;
        _positionController.text = existing.position ?? '';
        _departmentController.text = existing.department ?? '';
        _notesController.text = existing.notes ?? '';
        _isCurrent = existing.isCurrent;
        if (existing.startDate != null) {
          _startDate = DateTime.tryParse(existing.startDate!);
        }
        if (existing.endDate != null) {
          _endDate = DateTime.tryParse(existing.endDate!);
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('加载失败: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  void dispose() {
    _companyController.dispose();
    _positionController.dispose();
    _departmentController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(isEditing ? '编辑工作履历' : '添加工作履历'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios),
          onPressed: () => context.pop(),
        ),
        actions: [
          if (isEditing)
            IconButton(
              icon: _isDeleting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.delete_outline, color: Colors.red),
              onPressed: _isDeleting ? null : _handleDelete,
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  _buildSectionHeader('公司信息'),
                  const SizedBox(height: 12),
                  AppTextField(
                    controller: _companyController,
                    label: '公司名称 *',
                    hint: '请输入公司名称',
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return '请输入公司名称';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),
                  AppTextField(
                    controller: _positionController,
                    label: '职位',
                    hint: '请输入职位（选填）',
                  ),
                  const SizedBox(height: 16),
                  AppTextField(
                    controller: _departmentController,
                    label: '部门',
                    hint: '请输入部门（选填）',
                  ),

                  const SizedBox(height: 24),
                  _buildSectionHeader('任职时间'),
                  const SizedBox(height: 12),
                  _buildDatePicker(
                    label: '入职日期',
                    value: _startDate,
                    onSelect: (date) => setState(() => _startDate = date),
                  ),
                  const SizedBox(height: 16),
                  _buildCurrentSwitch(),
                  if (!_isCurrent) ...[
                    const SizedBox(height: 16),
                    _buildDatePicker(
                      label: '离职日期',
                      value: _endDate,
                      onSelect: (date) => setState(() => _endDate = date),
                    ),
                  ],

                  const SizedBox(height: 24),
                  _buildSectionHeader('备注'),
                  const SizedBox(height: 12),
                  AppTextField(
                    controller: _notesController,
                    label: '备注',
                    hint: '添加备注信息（选填）',
                    maxLines: 3,
                  ),

                  const SizedBox(height: 32),
                  AppButton(
                    text: isEditing ? '保存修改' : '添加',
                    isLoading: _isLoading,
                    onPressed: _handleSubmit,
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Text(
      title,
      style: AppTextStyles.headline6.copyWith(color: AppColors.primary),
    );
  }

  Widget _buildDatePicker({
    required String label,
    required DateTime? value,
    required ValueChanged<DateTime?> onSelect,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        InkWell(
          onTap: () async {
            final date = await showDatePicker(
              context: context,
              initialDate: value ?? DateTime.now(),
              firstDate: DateTime(1950),
              lastDate: DateTime.now().add(const Duration(days: 365)),
            );
            onSelect(date);
          },
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
            decoration: BoxDecoration(
              border: Border.all(color: AppColors.divider),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                Icon(Icons.calendar_today, size: 20, color: AppColors.textSecondary),
                const SizedBox(width: 12),
                Text(
                  value != null
                      ? '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}'
                      : '选择日期',
                  style: AppTextStyles.bodyText1.copyWith(
                    color: value != null ? AppColors.textPrimary : AppColors.textTertiary,
                  ),
                ),
                const Spacer(),
                if (value != null)
                  GestureDetector(
                    onTap: () => onSelect(null),
                    child: const Icon(Icons.clear, size: 18, color: AppColors.textTertiary),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildCurrentSwitch() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: _isCurrent ? AppColors.success.withValues(alpha: 0.1) : Colors.white,
        border: Border.all(
          color: _isCurrent ? AppColors.success : AppColors.divider,
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(
            _isCurrent ? Icons.check_circle : Icons.circle_outlined,
            color: _isCurrent ? AppColors.success : AppColors.textSecondary,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              '当前在职',
              style: AppTextStyles.bodyText1.copyWith(
                color: _isCurrent ? AppColors.success : AppColors.textPrimary,
              ),
            ),
          ),
          Switch(
            value: _isCurrent,
            onChanged: (value) {
              setState(() {
                _isCurrent = value;
                if (value) _endDate = null;
              });
            },
            activeColor: AppColors.success,
          ),
        ],
      ),
    );
  }

  String? _formatDate(DateTime? date) {
    if (date == null) return null;
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }

  Future<void> _handleSubmit() async {
    if (_formKey.currentState?.validate() ?? false) {
      setState(() => _isLoading = true);

      try {
        final workHistory = WorkHistoryModel(
          id: _existingWorkHistory?.id ?? '',
          memberId: widget.memberId,
          familyId: _existingWorkHistory?.familyId ?? '',
          companyName: _companyController.text,
          position: _positionController.text.isNotEmpty ? _positionController.text : null,
          department: _departmentController.text.isNotEmpty ? _departmentController.text : null,
          startDate: _formatDate(_startDate),
          endDate: _isCurrent ? null : _formatDate(_endDate),
          isCurrent: _isCurrent,
          notes: _notesController.text.isNotEmpty ? _notesController.text : null,
          createdAt: _existingWorkHistory?.createdAt ?? DateTime.now().toIso8601String(),
          updatedAt: DateTime.now().toIso8601String(),
        );

        if (isEditing) {
          await _dataSource.updateWorkHistory(widget.memberId, workHistory);
        } else {
          await _dataSource.createWorkHistory(widget.memberId, workHistory);
        }

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(isEditing ? '已保存' : '已添加')),
          );
          context.pop(true);
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('操作失败: $e'), backgroundColor: AppColors.error),
          );
        }
      } finally {
        if (mounted) setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _handleDelete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认删除'),
        content: const Text('确定要删除这条工作履历吗？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('删除'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      setState(() => _isDeleting = true);
      try {
        await _dataSource.deleteWorkHistory(widget.memberId, widget.workHistoryId!);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('已删除')),
          );
          context.pop(true);
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('删除失败: $e'), backgroundColor: AppColors.error),
          );
        }
      } finally {
        if (mounted) setState(() => _isDeleting = false);
      }
    }
  }
}
