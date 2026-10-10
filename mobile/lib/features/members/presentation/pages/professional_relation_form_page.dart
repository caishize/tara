import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:get_it/get_it.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/widgets/app_button.dart';
import '../../../../shared/widgets/app_text_field.dart';
import '../../data/datasources/member_remote_datasource.dart';
import '../../data/models/professional_relation_model.dart';
import '../../domain/entities/member.dart';
import '../bloc/members_bloc.dart';

class ProfessionalRelationFormPage extends StatefulWidget {
  final String memberId;
  final String? relationId;

  const ProfessionalRelationFormPage({
    super.key,
    required this.memberId,
    this.relationId,
  });

  @override
  State<ProfessionalRelationFormPage> createState() => _ProfessionalRelationFormPageState();
}

class _ProfessionalRelationFormPageState extends State<ProfessionalRelationFormPage> {
  final _formKey = GlobalKey<FormState>();
  final _companyController = TextEditingController();
  final _notesController = TextEditingController();

  late final MemberRemoteDataSource _dataSource;
  String? _selectedMemberId;
  String _selectedRelationType = 'peer';
  DateTime? _startDate;
  DateTime? _endDate;
  bool _isCurrent = true;
  bool _isLoading = false;
  bool _isDeleting = false;
  ProfessionalRelationModel? _existingRelation;
  List<Member> _members = [];

  bool get isEditing => widget.relationId != null;

  static const _relationTypes = [
    {'value': 'boss', 'label': '上级', 'icon': Icons.supervisor_account},
    {'value': 'subordinate', 'label': '下属', 'icon': Icons.person_outline},
    {'value': 'peer', 'label': '同事', 'icon': Icons.people},
    {'value': 'mentor', 'label': '导师', 'icon': Icons.school},
    {'value': 'mentee', 'label': '学员', 'icon': Icons.person_pin},
    {'value': 'client', 'label': '客户', 'icon': Icons.handshake},
    {'value': 'vendor', 'label': '供应商', 'icon': Icons.store},
    {'value': 'partner', 'label': '合作伙伴', 'icon': Icons.business_center},
    {'value': 'other', 'label': '其他', 'icon': Icons.person},
  ];

  @override
  void initState() {
    super.initState();
    _dataSource = GetIt.instance<MemberRemoteDataSource>();
    _loadMembers();
    if (isEditing) {
      _loadExistingData();
    }
  }

  void _loadMembers() {
    final state = context.read<MembersBloc>().state;
    if (state is MembersLoaded) {
      setState(() {
        // Filter out the current member from the list
        _members = state.members.where((m) => m.id != widget.memberId).toList();
      });
    }
  }

  Future<void> _loadExistingData() async {
    setState(() => _isLoading = true);
    try {
      final list = await _dataSource.getProfessionalRelations(widget.memberId);
      final existing = list.where((pr) => pr.id == widget.relationId).firstOrNull;
      if (existing != null) {
        _existingRelation = existing;
        _companyController.text = existing.companyName ?? '';
        _notesController.text = existing.notes ?? '';
        _selectedRelationType = existing.relationType;
        _isCurrent = existing.isCurrent;
        // Determine the other member
        _selectedMemberId = existing.fromMemberId == widget.memberId
            ? existing.toMemberId
            : existing.fromMemberId;
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
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(isEditing ? '编辑职业关系' : '添加职业关系'),
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
                  _buildSectionHeader('关系对象'),
                  const SizedBox(height: 12),
                  _buildMemberSelector(),

                  const SizedBox(height: 24),
                  _buildSectionHeader('关系类型'),
                  const SizedBox(height: 12),
                  _buildRelationTypeSelector(),

                  const SizedBox(height: 24),
                  _buildSectionHeader('共事公司'),
                  const SizedBox(height: 12),
                  AppTextField(
                    controller: _companyController,
                    label: '公司名称',
                    hint: '在哪个公司共事（选填）',
                  ),

                  const SizedBox(height: 24),
                  _buildSectionHeader('关系时间'),
                  const SizedBox(height: 12),
                  _buildDatePicker(
                    label: '开始时间',
                    value: _startDate,
                    onSelect: (date) => setState(() => _startDate = date),
                  ),
                  const SizedBox(height: 16),
                  _buildCurrentSwitch(),
                  if (!_isCurrent) ...[
                    const SizedBox(height: 16),
                    _buildDatePicker(
                      label: '结束时间',
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

  Widget _buildMemberSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('选择成员 *', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        if (_members.isEmpty)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.warning.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.warning),
            ),
            child: Row(
              children: [
                const Icon(Icons.warning_amber, color: AppColors.warning),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '请先添加其他家庭成员',
                    style: AppTextStyles.bodyText2.copyWith(color: AppColors.warning),
                  ),
                ),
              ],
            ),
          )
        else
          Container(
            decoration: BoxDecoration(
              border: Border.all(color: AppColors.divider),
              borderRadius: BorderRadius.circular(12),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _selectedMemberId,
                isExpanded: true,
                hint: const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 16),
                  child: Text('选择成员'),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 16),
                borderRadius: BorderRadius.circular(12),
                items: _members.map((member) {
                  return DropdownMenuItem(
                    value: member.id,
                    child: Row(
                      children: [
                        CircleAvatar(
                          radius: 16,
                          backgroundColor: AppColors.primary.withValues(alpha: 0.1),
                          child: Text(
                            member.name.isNotEmpty ? member.name[0] : '?',
                            style: TextStyle(
                              color: AppColors.primary,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text(member.name),
                        if (member.relation != 'other') ...[
                          const SizedBox(width: 8),
                          Text(
                            '(${member.relationText})',
                            style: AppTextStyles.caption.copyWith(
                              color: AppColors.textSecondary,
                            ),
                          ),
                        ],
                      ],
                    ),
                  );
                }).toList(),
                onChanged: (value) => setState(() => _selectedMemberId = value),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildRelationTypeSelector() {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: _relationTypes.map((type) {
        final isSelected = _selectedRelationType == type['value'];
        return ChoiceChip(
          avatar: Icon(
            type['icon'] as IconData,
            size: 18,
            color: isSelected ? AppColors.primary : AppColors.textSecondary,
          ),
          label: Text(type['label'] as String),
          selected: isSelected,
          onSelected: (_) => setState(() => _selectedRelationType = type['value'] as String),
          selectedColor: AppColors.primary.withValues(alpha: 0.2),
          labelStyle: TextStyle(
            color: isSelected ? AppColors.primary : AppColors.textSecondary,
          ),
        );
      }).toList(),
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
        color: _isCurrent ? AppColors.secondary.withValues(alpha: 0.1) : Colors.white,
        border: Border.all(
          color: _isCurrent ? AppColors.secondary : AppColors.divider,
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(
            _isCurrent ? Icons.check_circle : Icons.circle_outlined,
            color: _isCurrent ? AppColors.secondary : AppColors.textSecondary,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              '当前关系',
              style: AppTextStyles.bodyText1.copyWith(
                color: _isCurrent ? AppColors.secondary : AppColors.textPrimary,
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
            activeColor: AppColors.secondary,
          ),
        ],
      ),
    );
  }

  String? _formatDate(DateTime? date) {
    if (date == null) return null;
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }

  String _getRelationLabel(String type) {
    return _relationTypes.firstWhere(
      (t) => t['value'] == type,
      orElse: () => {'label': '其他'},
    )['label'] as String;
  }

  Future<void> _handleSubmit() async {
    if (_selectedMemberId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请选择关系对象')),
      );
      return;
    }

    if (_formKey.currentState?.validate() ?? false) {
      setState(() => _isLoading = true);

      try {
        final relation = ProfessionalRelationModel(
          id: _existingRelation?.id ?? '',
          familyId: _existingRelation?.familyId ?? '',
          fromMemberId: widget.memberId,
          toMemberId: _selectedMemberId!,
          relationType: _selectedRelationType,
          relationTypeLabel: _getRelationLabel(_selectedRelationType),
          companyName: _companyController.text.isNotEmpty ? _companyController.text : null,
          startDate: _formatDate(_startDate),
          endDate: _isCurrent ? null : _formatDate(_endDate),
          isCurrent: _isCurrent,
          notes: _notesController.text.isNotEmpty ? _notesController.text : null,
          createdAt: _existingRelation?.createdAt ?? DateTime.now().toIso8601String(),
          updatedAt: DateTime.now().toIso8601String(),
        );

        if (isEditing) {
          await _dataSource.updateProfessionalRelation(relation);
        } else {
          await _dataSource.createProfessionalRelation(relation);
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
        content: const Text('确定要删除这条职业关系吗？'),
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
        await _dataSource.deleteProfessionalRelation(widget.relationId!);
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
