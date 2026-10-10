import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../members/presentation/bloc/members_bloc.dart';
import '../../../members/domain/entities/member.dart';
import '../../domain/entities/gift.dart';

class GiftEntryPage extends StatefulWidget {
  const GiftEntryPage({super.key});

  @override
  State<GiftEntryPage> createState() => _GiftEntryPageState();
}

class _GiftEntryPageState extends State<GiftEntryPage> {
  @override
  void initState() {
    super.initState();
    // Load members for quick selection
    final membersBloc = context.read<MembersBloc>();
    if (membersBloc.state is! MembersLoaded) {
      membersBloc.add(const MembersLoadRequested());
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/dashboard');
            }
          },
        ),
        title: Text('礼物推荐', style: AppTextStyles.headline5),
        actions: [
          TextButton(
            onPressed: () => context.go('/discover'),
            child: Text(
              '更多',
              style: AppTextStyles.bodyText2.copyWith(color: AppColors.primary),
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _buildAIRecommendCard(),
          const SizedBox(height: 20),
          _buildQuickSelectSection(),
          const SizedBox(height: 20),
          _buildOccasionSection(),
        ],
      ),
    );
  }

  Widget _buildAIRecommendCard() {
    return GestureDetector(
      onTap: () => _showMemberSelectDialog(),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: AppColors.primaryGradient,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: AppColors.primary.withValues(alpha: 0.3),
              blurRadius: 12,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(
                Icons.auto_awesome,
                color: Colors.white,
                size: 28,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'AI 智能推荐',
                    style: AppTextStyles.headline5.copyWith(color: Colors.white),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '根据成员喜好和场景，智能推荐最合适的礼物',
                    style: AppTextStyles.caption.copyWith(
                      color: Colors.white.withValues(alpha: 0.9),
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.arrow_forward_ios,
              color: Colors.white,
              size: 16,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickSelectSection() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('为谁挑选礼物？', style: AppTextStyles.subtitle1),
          const SizedBox(height: 16),
          BlocBuilder<MembersBloc, MembersState>(
            builder: (context, state) {
              if (state is MembersLoading) {
                return const Center(
                  child: Padding(
                    padding: EdgeInsets.all(20),
                    child: CircularProgressIndicator(),
                  ),
                );
              }

              if (state is MembersLoaded) {
                if (state.members.isEmpty) {
                  return _buildEmptyMembersHint();
                }

                return Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: state.members.map((member) {
                    return _buildMemberChip(member);
                  }).toList(),
                );
              }

              return _buildEmptyMembersHint();
            },
          ),
        ],
      ),
    );
  }

  Widget _buildMemberChip(Member member) {
    return GestureDetector(
      onTap: () => context.push('/discover/recommend/${member.id}'),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.background,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.divider),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircleAvatar(
              radius: 16,
              backgroundColor: AppColors.primary.withValues(alpha: 0.1),
              child: Text(
                member.name.isNotEmpty ? member.name[0] : '?',
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.primary,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Text(member.name, style: AppTextStyles.bodyText2),
            const SizedBox(width: 4),
            const Icon(
              Icons.arrow_forward_ios,
              size: 12,
              color: AppColors.textTertiary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyMembersHint() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          const Icon(
            Icons.people_outline,
            size: 40,
            color: AppColors.textTertiary,
          ),
          const SizedBox(height: 12),
          Text(
            '暂无家庭成员',
            style: AppTextStyles.bodyText2.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: () => context.push('/members/form'),
            child: const Text('添加成员'),
          ),
        ],
      ),
    );
  }

  Widget _buildOccasionSection() {
    final occasions = [
      (icon: '🎂', label: '生日', occasion: GiftOccasion.birthday),
      (icon: '💑', label: '纪念日', occasion: GiftOccasion.anniversary),
      (icon: '🎉', label: '节日', occasion: GiftOccasion.holiday),
      (icon: '🎓', label: '毕业', occasion: GiftOccasion.graduation),
      (icon: '💒', label: '婚礼', occasion: GiftOccasion.wedding),
      (icon: '🙏', label: '感谢', occasion: GiftOccasion.thankyou),
    ];

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('按场合选择', style: AppTextStyles.subtitle1),
          const SizedBox(height: 16),
          GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 1.2,
            children: occasions.map((item) {
              return GestureDetector(
                onTap: () => _showMemberSelectDialog(preselectedOccasion: item.occasion),
                child: Container(
                  decoration: BoxDecoration(
                    color: AppColors.background,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(item.icon, style: const TextStyle(fontSize: 28)),
                      const SizedBox(height: 4),
                      Text(
                        item.label,
                        style: AppTextStyles.caption.copyWith(
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  void _showMemberSelectDialog({GiftOccasion? preselectedOccasion}) {
    final membersBloc = context.read<MembersBloc>();

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => BlocProvider.value(
        value: membersBloc,
        child: _MemberSelectSheet(
          preselectedOccasion: preselectedOccasion,
          onMemberSelected: (memberId) {
            Navigator.pop(sheetContext);
            context.push('/discover/recommend/$memberId');
          },
        ),
      ),
    );
  }
}

class _MemberSelectSheet extends StatefulWidget {
  final GiftOccasion? preselectedOccasion;
  final Function(String memberId) onMemberSelected;

  const _MemberSelectSheet({
    this.preselectedOccasion,
    required this.onMemberSelected,
  });

  @override
  State<_MemberSelectSheet> createState() => _MemberSelectSheetState();
}

class _MemberSelectSheetState extends State<_MemberSelectSheet> {
  Member? _selectedMember;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.6,
      ),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildHandle(),
          Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Text('选择成员', style: AppTextStyles.headline5),
                const Spacer(),
                GestureDetector(
                  onTap: () => Navigator.pop(context),
                  child: const Icon(Icons.close, color: AppColors.textSecondary),
                ),
              ],
            ),
          ),
          Flexible(
            child: BlocBuilder<MembersBloc, MembersState>(
              builder: (context, state) {
                if (state is MembersLoaded && state.members.isNotEmpty) {
                  return ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    itemCount: state.members.length,
                    itemBuilder: (context, index) {
                      final member = state.members[index];
                      final isSelected = _selectedMember?.id == member.id;

                      return GestureDetector(
                        onTap: () {
                          setState(() => _selectedMember = member);
                          // Auto-navigate after selection
                          Future.delayed(const Duration(milliseconds: 200), () {
                            widget.onMemberSelected(member.id);
                          });
                        },
                        child: Container(
                          margin: const EdgeInsets.only(bottom: 12),
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: isSelected ? AppColors.primary.withValues(alpha: 0.1) : AppColors.background,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isSelected ? AppColors.primary : Colors.transparent,
                              width: 2,
                            ),
                          ),
                          child: Row(
                            children: [
                              CircleAvatar(
                                radius: 20,
                                backgroundColor: AppColors.primary.withValues(alpha: 0.1),
                                child: Text(
                                  member.name.isNotEmpty ? member.name[0] : '?',
                                  style: AppTextStyles.subtitle1.copyWith(
                                    color: AppColors.primary,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(member.name, style: AppTextStyles.subtitle1),
                                    if (member.relation.isNotEmpty)
                                      Text(
                                        member.relation,
                                        style: AppTextStyles.caption.copyWith(
                                          color: AppColors.textSecondary,
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                              if (isSelected)
                                const Icon(
                                  Icons.check_circle,
                                  color: AppColors.primary,
                                ),
                            ],
                          ),
                        ),
                      );
                    },
                  );
                }

                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(40),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.people_outline,
                          size: 48,
                          color: AppColors.textTertiary,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          '暂无家庭成员',
                          style: AppTextStyles.bodyText1.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: () {
                            Navigator.pop(context);
                            context.push('/members/form');
                          },
                          child: const Text('添加成员'),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Widget _buildHandle() {
    return Container(
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
    );
  }
}
