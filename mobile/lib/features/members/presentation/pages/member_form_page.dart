import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/utils/relation_utils.dart';
import '../../../../shared/widgets/app_button.dart';
import '../../../../shared/widgets/app_text_field.dart';
import '../../domain/entities/member.dart';
import '../../data/models/member_model.dart';
import '../bloc/members_bloc.dart';

class MemberFormPage extends StatefulWidget {
  final String? memberId;

  const MemberFormPage({super.key, this.memberId});

  @override
  State<MemberFormPage> createState() => _MemberFormPageState();
}

class _MemberFormPageState extends State<MemberFormPage> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _nicknameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _emailController = TextEditingController();
  final _occupationController = TextEditingController();
  final _educationController = TextEditingController();
  final _hobbiesController = TextEditingController();
  final _giftPrefsController = TextEditingController();
  final _avoidItemsController = TextEditingController();

  String _selectedRelation = 'other';
  String? _selectedGender;
  DateTime? _selectedBirthDate;
  Member? _existingMember;
  bool _isLoading = false;
  final Set<String> _selectedProfessionalRelations = {};
  bool _showAllRelations = false; // Toggle for expanded view

  bool get isEditing => widget.memberId != null;

  @override
  void initState() {
    super.initState();
    if (isEditing) {
      _loadExistingMember();
    }
  }

  void _loadExistingMember() {
    // Populate from cached state immediately for perceived speed
    final state = context.read<MembersBloc>().state;
    if (state is MembersLoaded) {
      _populateFromMembers(state.members);
    }
    // Then trigger a fresh API fetch (state update handled by BlocListener)
    context.read<MembersBloc>().add(const MembersLoadRequested());
  }

  void _populateFromMembers(List<Member> members) {
    final member = members.where((m) => m.id == widget.memberId).firstOrNull;
    if (member != null) {
      _existingMember = member;
      _nameController.text = member.name;
      _nicknameController.text = member.nickname ?? '';
      _phoneController.text = member.phone ?? '';
      _emailController.text = member.email ?? '';
      _selectedRelation = member.relation;
      _selectedGender = member.gender;
      if (member.birthDate != null) {
        _selectedBirthDate = DateTime.tryParse(member.birthDate!);
      }
      // Profile
      _occupationController.text = member.profile?.occupation ?? '';
      _educationController.text = member.profile?.education ?? '';
      _hobbiesController.text = member.profile?.hobbies?.join(', ') ?? '';
      // Preferences
      _giftPrefsController.text = member.preferences?.giftPreferences?.join(', ') ?? '';
      _avoidItemsController.text = member.preferences?.avoidItems?.join(', ') ?? '';
      setState(() {});
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _nicknameController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    _occupationController.dispose();
    _educationController.dispose();
    _hobbiesController.dispose();
    _giftPrefsController.dispose();
    _avoidItemsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<MembersBloc, MembersState>(
      listener: (context, state) {
        if (state is MemberCreated) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(isEditing ? '成员已更新' : '成员已添加'),
              behavior: SnackBarBehavior.floating,
            ),
          );
          context.pop();
        } else if (state is MembersError) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(state.message),
              backgroundColor: AppColors.error,
              behavior: SnackBarBehavior.floating,
            ),
          );
          setState(() => _isLoading = false);
        } else if (state is MemberCreating) {
          setState(() => _isLoading = true);
        } else if (state is MembersLoaded && isEditing) {
          // Refresh form fields with fresh data from API
          _populateFromMembers(state.members);
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(isEditing ? '编辑成员' : '添加成员'),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios),
            onPressed: () => context.pop(),
          ),
        ),
        body: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              _buildSectionHeader('基本信息'),
              const SizedBox(height: 12),
              AppTextField(
                controller: _nameController,
                label: '姓名 *',
                hint: '请输入姓名',
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return '请输入姓名';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              AppTextField(
                controller: _nicknameController,
                label: '昵称',
                hint: '请输入昵称（选填）',
              ),
              const SizedBox(height: 16),
              _buildRelationSelector(),
              const SizedBox(height: 20),
              _buildProfessionalRelationsSelector(),
              const SizedBox(height: 16),
              _buildGenderSelector(),
              const SizedBox(height: 16),
              _buildBirthDatePicker(),

              const SizedBox(height: 24),
              _buildSectionHeader('联系方式'),
              const SizedBox(height: 12),
              AppTextField(
                controller: _phoneController,
                label: '手机号',
                hint: '请输入手机号（选填）',
                keyboardType: TextInputType.phone,
              ),
              const SizedBox(height: 16),
              AppTextField(
                controller: _emailController,
                label: '邮箱',
                hint: '请输入邮箱（选填）',
                keyboardType: TextInputType.emailAddress,
              ),

              const SizedBox(height: 24),
              _buildSectionHeader('个人档案'),
              const SizedBox(height: 12),
              AppTextField(
                controller: _occupationController,
                label: '职业',
                hint: '如：软件工程师、教师等',
              ),
              const SizedBox(height: 16),
              AppTextField(
                controller: _educationController,
                label: '学历',
                hint: '如：本科、硕士等',
              ),
              const SizedBox(height: 16),
              AppTextField(
                controller: _hobbiesController,
                label: '爱好',
                hint: '多个用逗号分隔，如：阅读, 旅游, 摄影',
              ),

              const SizedBox(height: 24),
              _buildSectionHeader('礼物偏好 (用于智能推荐)'),
              const SizedBox(height: 12),
              AppTextField(
                controller: _giftPrefsController,
                label: '喜欢的礼物类型',
                hint: '多个用逗号分隔，如：电子产品, 书籍, 护肤品',
              ),
              const SizedBox(height: 16),
              AppTextField(
                controller: _avoidItemsController,
                label: '不喜欢/避免的物品',
                hint: '多个用逗号分隔，如：香水, 花',
              ),

              const SizedBox(height: 32),
              AppButton(
                text: isEditing ? '保存修改' : '添加成员',
                isLoading: _isLoading,
                onPressed: _handleSubmit,
              ),
              const SizedBox(height: 20),
            ],
          ),
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

  Widget _buildRelationSelector() {
    // Get categories to display
    final categoriesToShow = _showAllRelations
        ? RelationUtils.relationCategories
        : RelationUtils.relationCategories.take(2).toList(); // Show first 2 categories by default

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('关系 *', style: AppTextStyles.subtitle2),
            TextButton(
              onPressed: () => setState(() => _showAllRelations = !_showAllRelations),
              child: Text(
                _showAllRelations ? '收起' : '展开更多',
                style: AppTextStyles.caption.copyWith(color: AppColors.primary),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ...categoriesToShow.map((category) {
          final options = category['options'] as List;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (_showAllRelations)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6, top: 8),
                  child: Text(
                    category['category'] as String,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textTertiary,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: options.map<Widget>((option) {
                  final value = option['value'] as String;
                  final label = option['label'] as String;
                  final isSelected = _selectedRelation == value;
                  return ChoiceChip(
                    label: Text(label),
                    selected: isSelected,
                    onSelected: (_) => setState(() => _selectedRelation = value),
                    selectedColor: AppColors.primary.withValues(alpha: 0.2),
                    labelStyle: TextStyle(
                      color: isSelected ? AppColors.primary : AppColors.textSecondary,
                      fontSize: 13,
                    ),
                  );
                }).toList(),
              ),
            ],
          );
        }),
        // Show currently selected if collapsed and not visible
        if (!_showAllRelations && !_isRelationInVisibleCategories(_selectedRelation))
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Chip(
              label: Text(
                RelationUtils.getRelationLabel(_selectedRelation),
                style: TextStyle(color: AppColors.primary, fontSize: 13),
              ),
              backgroundColor: AppColors.primary.withValues(alpha: 0.2),
              deleteIcon: Icon(Icons.close, size: 16, color: AppColors.primary),
              onDeleted: () => setState(() => _selectedRelation = 'other'),
            ),
          ),
      ],
    );
  }

  bool _isRelationInVisibleCategories(String relation) {
    final visibleCategories = RelationUtils.relationCategories.take(2);
    for (final category in visibleCategories) {
      final options = category['options'] as List;
      if (options.any((opt) => opt['value'] == relation)) {
        return true;
      }
    }
    return false;
  }

  Widget _buildProfessionalRelationsSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('职业关系', style: AppTextStyles.subtitle2),
            const SizedBox(width: 8),
            Text(
              '(可多选)',
              style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: RelationUtils.professionalRelationOptions.map((option) {
            final value = option['value']!;
            final label = option['label']!;
            final isSelected = _selectedProfessionalRelations.contains(value);
            return FilterChip(
              label: Text(label),
              selected: isSelected,
              onSelected: (selected) {
                setState(() {
                  if (selected) {
                    _selectedProfessionalRelations.add(value);
                  } else {
                    _selectedProfessionalRelations.remove(value);
                  }
                });
              },
              selectedColor: AppColors.secondary.withValues(alpha: 0.2),
              checkmarkColor: AppColors.secondary,
              labelStyle: TextStyle(
                color: isSelected ? AppColors.secondary : AppColors.textSecondary,
                fontSize: 13,
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildGenderSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('性别', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        Row(
          children: [
            _buildGenderChip('男', 'male'),
            const SizedBox(width: 12),
            _buildGenderChip('女', 'female'),
          ],
        ),
      ],
    );
  }

  Widget _buildGenderChip(String label, String value) {
    final isSelected = _selectedGender == value;
    return ChoiceChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (_) => setState(() => _selectedGender = value),
      selectedColor: AppColors.primary.withValues(alpha: 0.2),
      labelStyle: TextStyle(
        color: isSelected ? AppColors.primary : AppColors.textSecondary,
      ),
    );
  }

  Widget _buildBirthDatePicker() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('生日', style: AppTextStyles.subtitle2),
        const SizedBox(height: 8),
        InkWell(
          onTap: _selectBirthDate,
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
                  _selectedBirthDate != null
                      ? '${_selectedBirthDate!.year}-${_selectedBirthDate!.month.toString().padLeft(2, '0')}-${_selectedBirthDate!.day.toString().padLeft(2, '0')}'
                      : '选择日期',
                  style: AppTextStyles.bodyText1.copyWith(
                    color: _selectedBirthDate != null ? AppColors.textPrimary : AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _selectBirthDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _selectedBirthDate ?? DateTime(1990),
      firstDate: DateTime(1900),
      lastDate: DateTime.now(),
    );
    if (date != null) {
      setState(() => _selectedBirthDate = date);
    }
  }

  List<String> _parseCommaSeparated(String text) {
    if (text.trim().isEmpty) return [];
    return text.split(',').map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
  }

  void _handleSubmit() {
    if (_formKey.currentState?.validate() ?? false) {
      final hobbies = _parseCommaSeparated(_hobbiesController.text);
      final giftPrefs = _parseCommaSeparated(_giftPrefsController.text);
      final avoidItems = _parseCommaSeparated(_avoidItemsController.text);

      final profile = (_occupationController.text.isNotEmpty ||
              _educationController.text.isNotEmpty ||
              hobbies.isNotEmpty)
          ? MemberProfile(
              occupation: _occupationController.text.isNotEmpty ? _occupationController.text : null,
              education: _educationController.text.isNotEmpty ? _educationController.text : null,
              hobbies: hobbies.isNotEmpty ? hobbies : null,
            )
          : null;

      final preferences = (giftPrefs.isNotEmpty || avoidItems.isNotEmpty)
          ? MemberPreferences(
              giftPreferences: giftPrefs.isNotEmpty ? giftPrefs : null,
              avoidItems: avoidItems.isNotEmpty ? avoidItems : null,
            )
          : null;

      final member = MemberModel(
        id: isEditing ? widget.memberId! : '',
        name: _nameController.text,
        nickname: _nicknameController.text.isNotEmpty ? _nicknameController.text : null,
        gender: _selectedGender,
        birthDate: _selectedBirthDate != null
            ? '${_selectedBirthDate!.year}-${_selectedBirthDate!.month.toString().padLeft(2, '0')}-${_selectedBirthDate!.day.toString().padLeft(2, '0')}'
            : null,
        phone: _phoneController.text.isNotEmpty ? _phoneController.text : null,
        email: _emailController.text.isNotEmpty ? _emailController.text : null,
        relation: _selectedRelation,
        profile: profile,
        preferences: preferences,
        locations: _existingMember?.locations,
        defaultLocationType: _existingMember?.defaultLocationType,
        healthInfo: _existingMember?.healthInfo,
      );

      if (isEditing) {
        context.read<MembersBloc>().add(MemberUpdateRequested(member));
      } else {
        context.read<MembersBloc>().add(MemberCreateRequested(member));
      }
    }
  }
}
