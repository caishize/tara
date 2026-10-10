import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../members/presentation/bloc/members_bloc.dart';
import '../../../members/domain/entities/member.dart';
import '../../domain/entities/gift.dart';
import '../bloc/gifts_bloc.dart';
import '../widgets/gift_card.dart';

class GiftRecommendationPage extends StatefulWidget {
  final String memberId;
  final String? initialOccasion; // 从外部传入的初始场景（如从重要日期跳转）

  const GiftRecommendationPage({
    super.key,
    required this.memberId,
    this.initialOccasion,
  });

  @override
  State<GiftRecommendationPage> createState() => _GiftRecommendationPageState();
}

class _GiftRecommendationPageState extends State<GiftRecommendationPage> {
  Member? _member;
  GiftOccasion _selectedOccasion = GiftOccasion.birthday;
  int _selectedBudget = 500;
  String _selectedUrgency = 'normal';
  GiftRecommendation? _currentRecommendation;
  bool _hasInitialOccasion = false; // Track if occasion was set from external navigation

  final List<int> _budgetOptions = [100, 200, 300, 500, 800, 1000, 2000];
  final List<Map<String, String>> _urgencyOptions = [
    {'value': 'normal', 'label': '普通'},
    {'value': 'urgent', 'label': '紧急 (< 3天)'},
  ];

  @override
  void initState() {
    super.initState();
    // Clear any previous recommendation that might be for a different member
    _currentRecommendation = null;
    _loadMember();

    // Initialize occasion from passed parameter (e.g., from important date page)
    if (widget.initialOccasion != null) {
      _selectedOccasion = _parseOccasion(widget.initialOccasion!);
      _hasInitialOccasion = true; // Mark that occasion was explicitly set
    } else {
      // Or from bloc state if already loaded (e.g., when navigating back)
      final giftsState = context.read<GiftsBloc>().state;
      if (giftsState is GiftsLoaded && giftsState.selectedSmartDate != null) {
        _selectedOccasion = giftsState.selectedSmartDate!.occasionType;
      }
    }

    // Load recommendation history for this member
    context.read<GiftsBloc>().add(RecommendationHistoryLoadRequested(memberId: widget.memberId));
    // Load member gift memory and history
    context.read<GiftsBloc>().add(MemberGiftMemoryLoadRequested(memberId: widget.memberId));
    context.read<GiftsBloc>().add(MemberGiftHistoryLoadRequested(memberId: widget.memberId));
    // Load smart dates for this member
    context.read<GiftsBloc>().add(SmartDatesLoadRequested(memberId: widget.memberId));
    // Load budget suggestion for this member (with initial occasion if provided)
    context.read<GiftsBloc>().add(BudgetSuggestionLoadRequested(
      memberId: widget.memberId,
      occasion: widget.initialOccasion ?? _selectedOccasion.name,
    ));
  }

  /// 解析场景字符串为枚举
  GiftOccasion _parseOccasion(String occasion) {
    switch (occasion.toLowerCase()) {
      case 'birthday':
        return GiftOccasion.birthday;
      case 'anniversary':
        return GiftOccasion.anniversary;
      case 'holiday':
        return GiftOccasion.holiday;
      case 'graduation':
        return GiftOccasion.graduation;
      case 'wedding':
        return GiftOccasion.wedding;
      case 'babyshower':
      case 'baby_shower':
        return GiftOccasion.babyShower;
      case 'housewarming':
        return GiftOccasion.housewarming;
      case 'thankyou':
      case 'thank_you':
        return GiftOccasion.thankyou;
      default:
        return GiftOccasion.other;
    }
  }

  void _loadMember() {
    final membersState = context.read<MembersBloc>().state;
    if (membersState is MembersLoaded) {
      final found = membersState.members.where((m) => m.id == widget.memberId);
      if (found.isNotEmpty) {
        _member = found.first;
      } else {
        _member = Member(
          id: widget.memberId,
          name: '未知成员',
        );
      }
      setState(() {});
    } else {
      // Members not loaded yet, trigger a load
      context.read<MembersBloc>().add(const MembersLoadRequested());
    }
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocListener(
      listeners: [
        // Listen for members loading to update the member info
        BlocListener<MembersBloc, MembersState>(
          listener: (context, state) {
            if (state is MembersLoaded && _member == null) {
              _loadMember();
            }
          },
        ),
        // Listen for smart dates auto-selection
        BlocListener<GiftsBloc, GiftsState>(
          listenWhen: (previous, current) {
            // Listen when smart dates are loaded and auto-selected
            // Only trigger when going from no selection to a selection (auto-select on load)
            if (previous is GiftsLoaded && current is GiftsLoaded) {
              // Only sync when smart date is newly selected (not when cleared)
              return previous.selectedSmartDate == null && current.selectedSmartDate != null;
            }
            if (previous is! GiftsLoaded && current is GiftsLoaded) {
              return current.selectedSmartDate != null;
            }
            return false;
          },
          listener: (context, state) {
            // Sync local occasion state with auto-selected smart date
            // BUT skip this if occasion was explicitly set from external navigation (e.g., from important date page)
            if (_hasInitialOccasion) {
              // Reset flag after first load, so user can still interact with smart dates
              _hasInitialOccasion = false;
              return;
            }
            if (state is GiftsLoaded && state.selectedSmartDate != null) {
              final newOccasion = state.selectedSmartDate!.occasionType;
              if (_selectedOccasion != newOccasion) {
                setState(() {
                  _selectedOccasion = newOccasion;
                });
              }
            }
          },
        ),
      ],
      child: Scaffold(
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
        ),
        body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _buildMemberCard(),
          const SizedBox(height: 20),
          _buildMemberPreferencesCard(),
          const SizedBox(height: 20),
          _buildSmartDatesSection(),
          const SizedBox(height: 20),
          _buildOccasionSection(),
          const SizedBox(height: 20),
          _buildBudgetSection(),
          const SizedBox(height: 16),
          _buildUrgencySection(),
          const SizedBox(height: 24),
          _buildRecommendButton(),
          const SizedBox(height: 24),
          _buildRecommendedGifts(),
          const SizedBox(height: 24),
          _buildMemberGiftHistory(),
          const SizedBox(height: 24),
          _buildRecommendationHistory(),
        ],
      ),
      ),
    );
  }

  Widget _buildMemberCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 28,
            backgroundColor: Colors.white.withValues(alpha: 0.2),
            child: Text(
              _member?.name.isNotEmpty == true ? _member!.name[0] : '?',
              style: AppTextStyles.headline5.copyWith(color: Colors.white),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '为 ${_member?.name ?? '加载中...'} 推荐礼物',
                  style: AppTextStyles.subtitle1.copyWith(color: Colors.white),
                ),
                if (_member != null && _member!.relation.isNotEmpty)
                  Text(
                    _member!.relation,
                    style: AppTextStyles.caption.copyWith(
                      color: Colors.white.withValues(alpha: 0.8),
                    ),
                  ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.card_giftcard, color: Colors.white, size: 24),
          ),
        ],
      ),
    );
  }

  Widget _buildSmartDatesSection() {
    return BlocBuilder<GiftsBloc, GiftsState>(
      builder: (context, state) {
        List<SmartDate> smartDates = [];
        SmartDate? selectedDate;

        if (state is GiftsLoaded) {
          smartDates = state.smartDates;
          selectedDate = state.selectedSmartDate;
        }

        if (smartDates.isEmpty) {
          return const SizedBox.shrink();
        }

        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [AppColors.shadowLight],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.event, color: AppColors.primary, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text('智能日期推荐', style: AppTextStyles.subtitle1),
                  ),
                  if (selectedDate != null && !selectedDate.isGeneral)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        selectedDate.countdownText,
                        style: AppTextStyles.caption.copyWith(color: AppColors.primary),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                '选择日期后自动匹配场合',
                style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
              ),
              const SizedBox(height: 12),
              SizedBox(
                height: 80,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: smartDates.length,
                  separatorBuilder: (context, index) => const SizedBox(width: 10),
                  itemBuilder: (context, index) {
                    final date = smartDates[index];
                    final isSelected = selectedDate?.id == date.id &&
                                       selectedDate?.name == date.name;
                    return _buildSmartDateCard(date, isSelected);
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildSmartDateCard(SmartDate date, bool isSelected) {
    final Color cardColor;
    if (isSelected) {
      cardColor = AppColors.primary;
    } else {
      switch (date.source) {
        case SmartDateSource.memberDate:
          cardColor = AppColors.accent1;
        case SmartDateSource.naturalHoliday:
          cardColor = AppColors.accent2;
        case SmartDateSource.general:
          cardColor = AppColors.textTertiary;
      }
    }

    return GestureDetector(
      onTap: () => _onSmartDateSelected(date),
      child: Container(
        width: 90,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: isSelected ? cardColor : cardColor.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? cardColor : cardColor.withValues(alpha: 0.3),
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              date.icon,
              style: const TextStyle(fontSize: 22),
            ),
            const SizedBox(height: 4),
            Text(
              date.name,
              style: AppTextStyles.caption.copyWith(
                color: isSelected ? Colors.white : cardColor,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              ),
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            if (date.daysUntil != null && date.daysUntil! >= 0) ...[
              const SizedBox(height: 2),
              Text(
                date.countdownText,
                style: TextStyle(
                  fontSize: 10,
                  color: isSelected ? Colors.white.withValues(alpha: 0.8) : AppColors.textTertiary,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _onSmartDateSelected(SmartDate date) {
    // Update bloc state
    context.read<GiftsBloc>().add(SmartDateSelected(date: date));

    // Update local occasion selection based on smart date
    setState(() {
      _selectedOccasion = date.occasionType;
    });

    // Reload budget suggestion with the new occasion
    context.read<GiftsBloc>().add(BudgetSuggestionLoadRequested(
      memberId: widget.memberId,
      occasion: date.occasionType.name,
    ));
  }

  void _onOccasionManuallySelected(GiftOccasion occasion) {
    // Update local state
    setState(() {
      _selectedOccasion = occasion;
    });

    // Clear smart date selection since user is manually choosing occasion
    context.read<GiftsBloc>().add(const SmartDateSelected(date: null));

    // Reload budget suggestion with the new occasion
    context.read<GiftsBloc>().add(BudgetSuggestionLoadRequested(
      memberId: widget.memberId,
      occasion: occasion.name,
    ));
  }

  Widget _buildOccasionSection() {
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
          Text('送礼场合', style: AppTextStyles.subtitle1),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: GiftOccasion.values.map((occasion) {
              final isSelected = _selectedOccasion == occasion;
              return GestureDetector(
                onTap: () => _onOccasionManuallySelected(occasion),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: isSelected ? AppColors.primary : AppColors.background,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: isSelected ? AppColors.primary : AppColors.divider,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_getOccasionIcon(occasion), style: const TextStyle(fontSize: 14)),
                      const SizedBox(width: 4),
                      Text(
                        _getOccasionName(occasion),
                        style: AppTextStyles.bodyText2.copyWith(
                          color: isSelected ? Colors.white : AppColors.textPrimary,
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

  Widget _buildBudgetSection() {
    return BlocBuilder<GiftsBloc, GiftsState>(
      builder: (context, state) {
        BudgetSuggestion? suggestion;
        if (state is GiftsLoaded) {
          suggestion = state.budgetSuggestion;
        }

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
              Row(
                children: [
                  Text('预算范围', style: AppTextStyles.subtitle1),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.error.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '¥$_selectedBudget',
                      style: AppTextStyles.bodyText2.copyWith(
                        color: AppColors.error,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                '推荐范围: ¥${(_selectedBudget * 0.5).round()} - ¥$_selectedBudget',
                style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
              ),
              // Budget suggestion from AI
              if (suggestion != null) ...[
                const SizedBox(height: 8),
                _buildBudgetSuggestionHint(suggestion),
              ],
              const SizedBox(height: 12),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: _budgetOptions.map((budget) {
                  final isSelected = _selectedBudget == budget;
                  final isSuggested = suggestion != null &&
                      _isNearSuggestedBudget(budget, suggestion.suggestedBudget);
                  return GestureDetector(
                    onTap: () => setState(() => _selectedBudget = budget),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(
                        color: isSelected ? AppColors.accent1 : AppColors.background,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: isSelected
                              ? AppColors.accent1
                              : (isSuggested ? AppColors.success : AppColors.divider),
                          width: isSuggested && !isSelected ? 2 : 1,
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            '¥$budget',
                            style: AppTextStyles.bodyText2.copyWith(
                              color: isSelected ? Colors.white : AppColors.textPrimary,
                            ),
                          ),
                          if (isSuggested && !isSelected) ...[
                            const SizedBox(width: 4),
                            const Icon(Icons.recommend, size: 14, color: AppColors.success),
                          ],
                        ],
                      ),
                    ),
                  );
                }).toList(),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildBudgetSuggestionHint(BudgetSuggestion suggestion) {
    return GestureDetector(
      onTap: () => _applySuggestedBudget(suggestion.suggestedBudget),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.success.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppColors.success.withValues(alpha: 0.3)),
        ),
        child: Row(
          children: [
            const Icon(Icons.auto_awesome, color: AppColors.success, size: 16),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '建议预算: ¥${suggestion.suggestedBudget}',
                    style: AppTextStyles.bodyText2.copyWith(
                      color: AppColors.success,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    '参考范围: ¥${suggestion.budgetMin} - ¥${suggestion.budgetMax} · 置信度: ${suggestion.confidenceLevel}',
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.success.withValues(alpha: 0.8),
                      fontSize: 10,
                    ),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.success,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                '应用',
                style: AppTextStyles.caption.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  bool _isNearSuggestedBudget(int budget, int suggested) {
    // Consider a budget "near" if it's within 20% of the suggested amount
    final diff = (budget - suggested).abs();
    return diff <= suggested * 0.2;
  }

  void _applySuggestedBudget(int suggestedBudget) {
    // Find the closest budget option
    int closest = _budgetOptions.first;
    int minDiff = (closest - suggestedBudget).abs();

    for (final budget in _budgetOptions) {
      final diff = (budget - suggestedBudget).abs();
      if (diff < minDiff) {
        minDiff = diff;
        closest = budget;
      }
    }

    setState(() {
      _selectedBudget = closest;
    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('已应用建议预算 ¥$closest'),
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  Widget _buildUrgencySection() {
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
          Text('紧急程度', style: AppTextStyles.subtitle1),
          const SizedBox(height: 12),
          Row(
            children: _urgencyOptions.map((option) {
              final isSelected = _selectedUrgency == option['value'];
              return Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _selectedUrgency = option['value']!),
                  child: Container(
                    margin: EdgeInsets.only(right: option == _urgencyOptions.last ? 0 : 10),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? (option['value'] == 'urgent' ? AppColors.error : AppColors.primary)
                          : AppColors.background,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: isSelected
                            ? (option['value'] == 'urgent' ? AppColors.error : AppColors.primary)
                            : AppColors.divider,
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          option['value'] == 'urgent' ? Icons.bolt : Icons.schedule,
                          size: 16,
                          color: isSelected ? Colors.white : AppColors.textSecondary,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          option['label']!,
                          style: AppTextStyles.bodyText2.copyWith(
                            color: isSelected ? Colors.white : AppColors.textPrimary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildMemberPreferencesCard() {
    return BlocBuilder<GiftsBloc, GiftsState>(
      builder: (context, state) {
        MemberGiftMemory? memory;
        if (state is GiftsLoaded) {
          memory = state.memberMemory;
        }

        if (memory == null ||
            (memory.likedCategories.isEmpty &&
                memory.dislikedCategories.isEmpty &&
                memory.giftsToAvoid.isEmpty &&
                memory.recentGifts.isEmpty)) {
          return const SizedBox.shrink();
        }

        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.info.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.info.withValues(alpha: 0.3)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.psychology, color: AppColors.info, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${_member?.name ?? ''}的偏好记忆',
                      style: AppTextStyles.subtitle2.copyWith(color: AppColors.info),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              if (memory.likedCategories.isNotEmpty) ...[
                _buildPreferenceRow('👍 喜欢', memory.likedCategories, AppColors.success),
                const SizedBox(height: 8),
              ],
              if (memory.dislikedCategories.isNotEmpty) ...[
                _buildPreferenceRow('👎 不喜欢', memory.dislikedCategories, AppColors.error),
                const SizedBox(height: 8),
              ],
              if (memory.giftsToAvoid.isNotEmpty) ...[
                _buildPreferenceRow('⚠️ 避免重复', memory.giftsToAvoid.take(3).toList(), AppColors.warning),
                const SizedBox(height: 8),
              ],
              if (memory.interestKeywords.isNotEmpty) ...[
                _buildPreferenceRow('✨ 兴趣', memory.interestKeywords.take(5).toList(), AppColors.primary),
              ],
            ],
          ),
        );
      },
    );
  }

  Widget _buildPreferenceRow(String label, List<String> items, Color color) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 80,
          child: Text(
            label,
            style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
          ),
        ),
        Expanded(
          child: Wrap(
            spacing: 6,
            runSpacing: 4,
            children: items.map((item) {
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  item,
                  style: AppTextStyles.caption.copyWith(
                    color: color,
                    fontSize: 11,
                  ),
                ),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildMemberGiftHistory() {
    return BlocBuilder<GiftsBloc, GiftsState>(
      builder: (context, state) {
        List<GiftHistoryItem> history = [];
        if (state is GiftsLoaded) {
          history = state.memberGiftHistory;
        }

        if (history.isEmpty) {
          return const SizedBox.shrink();
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.history, size: 20, color: AppColors.textSecondary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '已送过的礼物 (避免重复)',
                    style: AppTextStyles.subtitle1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Text(
                  '${history.length} 件',
                  style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.warning.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.warning.withValues(alpha: 0.3)),
              ),
              child: Column(
                children: history.take(5).map((item) => _buildHistoryItemRow(item)).toList(),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildHistoryItemRow(GiftHistoryItem item) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: AppColors.warning.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Center(
              child: Text('🎁', style: TextStyle(fontSize: 14)),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.giftName,
                  style: AppTextStyles.bodyText2,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  '${item.occasion} · ¥${item.price.toStringAsFixed(0)}',
                  style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
                ),
              ],
            ),
          ),
          Text(
            _formatHistoryDate(item.giftDate),
            style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
          ),
        ],
      ),
    );
  }

  String _formatHistoryDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);
    if (diff.inDays < 30) return '${diff.inDays}天前';
    if (diff.inDays < 365) return '${(diff.inDays / 30).round()}个月前';
    return '${(diff.inDays / 365).round()}年前';
  }

  Widget _buildRecommendButton() {
    return BlocBuilder<GiftsBloc, GiftsState>(
      builder: (context, state) {
        final isLoading = state is GiftsLoading;

        return SizedBox(
          width: double.infinity,
          height: 52,
          child: ElevatedButton(
            onPressed: isLoading ? null : _getRecommendations,
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              elevation: 4,
              shadowColor: AppColors.primary.withValues(alpha: 0.3),
            ),
            child: isLoading
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                  )
                : Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.auto_awesome, color: Colors.white, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        'AI 智能推荐',
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

  Widget _buildRecommendedGifts() {
    return BlocConsumer<GiftsBloc, GiftsState>(
      listener: (context, state) {
        // Store recommendation result for display - only if it's for the current member
        if (state is GiftRecommendationLoaded) {
          final rec = state.recommendation;
          // Only set if the recommendation is for the current member
          if (rec.memberId == widget.memberId) {
            setState(() {
              _currentRecommendation = rec;
            });
          }
        } else if (state is GiftsLoaded && state.currentRecommendation != null) {
          final rec = state.currentRecommendation!;
          // Only set if the recommendation is for the current member
          if (rec.memberId == widget.memberId) {
            setState(() {
              _currentRecommendation = rec;
            });
          }
        } else if (state is GiftsError) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('推荐失败: ${state.message}'),
              backgroundColor: AppColors.error,
            ),
          );
        }
      },
      builder: (context, state) {
        // Show loading state
        if (state is GiftsLoading) {
          return Container(
            padding: const EdgeInsets.all(32),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [AppColors.shadowLight],
            ),
            child: Column(
              children: [
                const CircularProgressIndicator(),
                const SizedBox(height: 16),
                Text(
                  'AI 正在为您智能推荐...',
                  style: AppTextStyles.bodyText1.copyWith(color: AppColors.textSecondary),
                ),
                const SizedBox(height: 8),
                Text(
                  '正在分析成员偏好和历史数据',
                  style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
                ),
              ],
            ),
          );
        }

        // Show recommendation results
        if (_currentRecommendation != null && _currentRecommendation!.gifts.isNotEmpty) {
          final gifts = _currentRecommendation!.gifts;

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Result header
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.success.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.auto_awesome, color: AppColors.success, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '为 ${_currentRecommendation!.memberName} 推荐 ${_getOccasionName(_currentRecommendation!.occasion)}礼物',
                        style: AppTextStyles.bodyText2.copyWith(color: AppColors.success),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Text('推荐礼物', style: AppTextStyles.subtitle1),
                  const Spacer(),
                  Text(
                    '${gifts.length} 个结果',
                    style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  childAspectRatio: 0.65,
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 12,
                ),
                itemCount: gifts.length,
                itemBuilder: (context, index) => GiftCard(
                  gift: gifts[index],
                  onTap: () => _openPurchaseUrl(gifts[index]),
                ),
              ),
            ],
          );
        }

        // Show error state
        if (state is GiftsError) {
          return Container(
            padding: const EdgeInsets.all(32),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [AppColors.shadowLight],
            ),
            child: Column(
              children: [
                const Icon(Icons.error_outline, size: 48, color: AppColors.error),
                const SizedBox(height: 16),
                Text(
                  '推荐失败',
                  style: AppTextStyles.bodyText1.copyWith(color: AppColors.error),
                ),
                const SizedBox(height: 8),
                Text(
                  state.message,
                  style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                TextButton(
                  onPressed: _getRecommendations,
                  child: const Text('重试'),
                ),
              ],
            ),
          );
        }

        return _buildNoGiftsHint();
      },
    );
  }

  Widget _buildNoGiftsHint() {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        children: [
          const Icon(Icons.card_giftcard_outlined, size: 48, color: AppColors.textTertiary),
          const SizedBox(height: 16),
          Text(
            '点击上方按钮获取推荐',
            style: AppTextStyles.bodyText1.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 8),
          Text(
            '我们将根据成员喜好和预算\n为您智能推荐合适的礼物',
            style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildRecommendationHistory() {
    return BlocBuilder<GiftsBloc, GiftsState>(
      builder: (context, state) {
        List<GiftRecommendation> history = [];

        if (state is GiftsLoaded && state.history.isNotEmpty) {
          // Filter history to only show recommendations for the current member
          history = state.history
              .where((rec) => rec.memberId == widget.memberId)
              .toList();
        }

        if (history.isEmpty) {
          return const SizedBox.shrink();
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.history, size: 20, color: AppColors.textSecondary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '${_member?.name ?? ''}的历史推荐',
                    style: AppTextStyles.subtitle1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Text(
                  '${history.length} 条',
                  style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: history.length > 5 ? 5 : history.length,
              separatorBuilder: (context, index) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final rec = history[index];
                return _buildHistoryCard(rec);
              },
            ),
          ],
        );
      },
    );
  }

  Widget _buildHistoryCard(GiftRecommendation rec) {
    return GestureDetector(
      onTap: () {
        // Show the historical recommendation
        setState(() {
          _currentRecommendation = rec;
        });
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [AppColors.shadowLight],
        ),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Center(
                child: Text(
                  _getOccasionIcon(rec.occasion),
                  style: const TextStyle(fontSize: 24),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${rec.memberName} - ${_getOccasionName(rec.occasion)}',
                    style: AppTextStyles.subtitle2,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${rec.gifts.length} 个推荐 · ${_formatDate(rec.createdAt)}',
                    style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: AppColors.textTertiary),
          ],
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inDays == 0) {
      return '今天';
    } else if (diff.inDays == 1) {
      return '昨天';
    } else if (diff.inDays < 7) {
      return '${diff.inDays}天前';
    } else {
      return '${date.month}月${date.day}日';
    }
  }

  void _getRecommendations() {
    if (_member == null) return;

    // Calculate budget range: budgetMin is 50% of selected budget
    // This ensures recommendations are close to the selected budget, not just under it
    final budgetMin = (_selectedBudget * 0.5).round();

    // Call real AI recommendation API
    context.read<GiftsBloc>().add(GiftRecommendationRequested(
      memberId: _member!.id,
      occasion: _selectedOccasion,
      budgetMin: budgetMin,
      budgetMax: _selectedBudget,
      urgency: _selectedUrgency,
    ));
  }

  Future<void> _openPurchaseUrl(Gift gift) async {
    final url = gift.purchaseUrl;
    if (url == null || url.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('暂无购买链接: ${gift.name}'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('无法打开链接: $url'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  String _getOccasionIcon(GiftOccasion occasion) {
    switch (occasion) {
      case GiftOccasion.birthday: return '🎂';
      case GiftOccasion.anniversary: return '💑';
      case GiftOccasion.holiday: return '🎉';
      case GiftOccasion.graduation: return '🎓';
      case GiftOccasion.wedding: return '💒';
      case GiftOccasion.babyShower: return '👶';
      case GiftOccasion.housewarming: return '🏠';
      case GiftOccasion.thankyou: return '🙏';
      case GiftOccasion.other: return '🎁';
    }
  }

  String _getOccasionName(GiftOccasion occasion) {
    switch (occasion) {
      case GiftOccasion.birthday: return '生日';
      case GiftOccasion.anniversary: return '纪念日';
      case GiftOccasion.holiday: return '节日';
      case GiftOccasion.graduation: return '毕业';
      case GiftOccasion.wedding: return '婚礼';
      case GiftOccasion.babyShower: return '满月';
      case GiftOccasion.housewarming: return '乔迁';
      case GiftOccasion.thankyou: return '感谢';
      case GiftOccasion.other: return '其他';
    }
  }
}
