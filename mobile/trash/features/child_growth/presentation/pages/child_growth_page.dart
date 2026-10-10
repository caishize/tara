import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../members/presentation/bloc/members_bloc.dart';
import '../../../members/domain/entities/member.dart';
import '../../domain/entities/vaccine.dart';
import '../bloc/child_growth_bloc.dart';
import '../widgets/growth_summary_card.dart';
import '../widgets/growth_chart.dart';
import '../widgets/milestone_timeline.dart';
import '../widgets/vaccine_schedule.dart';
import '../widgets/add_growth_record_sheet.dart';
import '../widgets/add_milestone_sheet.dart';

class ChildGrowthPage extends StatefulWidget {
  /// Optional member ID to pre-select when navigating from member detail page
  final String? initialMemberId;

  /// Optional initial tab index (0=overview, 1=growth, 2=milestones, 3=vaccines)
  final int initialTab;

  const ChildGrowthPage({super.key, this.initialMemberId, this.initialTab = 0});

  @override
  State<ChildGrowthPage> createState() => _ChildGrowthPageState();
}

class _ChildGrowthPageState extends State<ChildGrowthPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  Member? _selectedChild;
  bool _hasAutoSelected = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this, initialIndex: widget.initialTab);
    _tabController.addListener(_onTabChanged);

    // 加载家庭成员
    final membersBloc = context.read<MembersBloc>();
    if (membersBloc.state is! MembersLoaded) {
      membersBloc.add(const MembersLoadRequested());
    } else {
      // Members already loaded, try to auto-select
      _tryAutoSelectChild(membersBloc.state as MembersLoaded);
    }
  }

  /// Try to auto-select the child if initialMemberId is provided
  void _tryAutoSelectChild(MembersLoaded state) {
    if (_hasAutoSelected || widget.initialMemberId == null) return;

    final children = state.members.where((m) => m.isChild).toList();
    final targetChild = children.where((m) => m.id == widget.initialMemberId).firstOrNull;

    if (targetChild != null) {
      _hasAutoSelected = true;
      // Use addPostFrameCallback to avoid calling setState during build
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _loadChildData(targetChild);
      });
    }
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (!_tabController.indexIsChanging) {
      context.read<ChildGrowthBloc>().add(
        ChildGrowthTabChanged(tabIndex: _tabController.index),
      );
    }
  }

  void _loadChildData(Member child) {
    setState(() {
      _selectedChild = child;
    });
    context.read<ChildGrowthBloc>().add(
      ChildGrowthLoadRequested(childId: child.id),
    );
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<MembersBloc, MembersState>(
      listener: (context, state) {
        // Auto-select child when members finish loading
        if (state is MembersLoaded && widget.initialMemberId != null) {
          _tryAutoSelectChild(state);
        }
      },
      child: Scaffold(
        backgroundColor: AppColors.background,
        body: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              _buildChildSelector(),
              _buildTabBar(),
              Expanded(child: _buildContent()),
            ],
          ),
        ),
        floatingActionButton: _selectedChild != null
            ? FloatingActionButton.extended(
                onPressed: () => _showAddDialog(context),
                backgroundColor: AppColors.primary,
                icon: const Icon(Icons.add, color: Colors.white),
                label: Text(
                  _getAddButtonLabel(),
                  style: const TextStyle(color: Colors.white),
                ),
              )
            : null,
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.child_care, color: Colors.white, size: 28),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('宝宝成长', style: AppTextStyles.headline5),
                const SizedBox(height: 2),
                Text(
                  '记录宝宝的每一个成长瞬间',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          if (_selectedChild != null)
            BlocBuilder<ChildGrowthBloc, ChildGrowthState>(
              builder: (context, state) {
                if (state is ChildGrowthLoaded && state.overdueVaccines.isNotEmpty) {
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.error.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.warning, size: 16, color: AppColors.error),
                        const SizedBox(width: 4),
                        Text(
                          '${state.overdueVaccines.length}个疫苗过期',
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.error,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  );
                }
                return const SizedBox.shrink();
              },
            ),
        ],
      ),
    );
  }

  Widget _buildChildSelector() {
    return BlocBuilder<MembersBloc, MembersState>(
      builder: (context, state) {
        if (state is MembersLoading) {
          return const Padding(
            padding: EdgeInsets.symmetric(horizontal: 20),
            child: Center(child: CircularProgressIndicator()),
          );
        }

        if (state is MembersLoaded) {
          // 筛选出孩子（根据relation或age判断）
          final children = state.members.where((m) {
            final relationship = m.relation.toLowerCase();
            return relationship.contains('child') ||
                relationship.contains('son') ||
                relationship.contains('daughter') ||
                relationship == 'kid' ||
                relationship == 'grandchild' ||
                (m.age != null && m.age! <= 12);
          }).toList();

          if (children.isEmpty) {
            return Container(
              margin: const EdgeInsets.symmetric(horizontal: 20),
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppColors.inputBackground,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                children: [
                  const Icon(Icons.child_friendly, size: 48, color: AppColors.textTertiary),
                  const SizedBox(height: 12),
                  Text(
                    '暂无宝宝信息',
                    style: AppTextStyles.subtitle1.copyWith(color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '请先在家庭成员中添加宝宝',
                    style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
                  ),
                ],
              ),
            );
          }

          // 如果还没选择宝宝，默认选择第一个
          if (_selectedChild == null && children.isNotEmpty) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              _loadChildData(children.first);
            });
          }

          return Container(
            height: 44,
            margin: const EdgeInsets.only(bottom: 8),
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: children.length,
              itemBuilder: (context, index) {
                final child = children[index];
                final isSelected = _selectedChild?.id == child.id;
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: GestureDetector(
                    onTap: () => _loadChildData(child),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(
                        color: isSelected ? AppColors.primary : Colors.white,
                        borderRadius: BorderRadius.circular(22),
                        border: Border.all(
                          color: isSelected ? AppColors.primary : AppColors.divider,
                        ),
                        boxShadow: isSelected ? [AppColors.shadowLight] : null,
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          CircleAvatar(
                            radius: 12,
                            backgroundColor: isSelected
                                ? Colors.white.withValues(alpha: 0.2)
                                : AppColors.primary.withValues(alpha: 0.1),
                            child: Text(
                              child.name.isNotEmpty ? child.name[0] : '?',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: isSelected ? Colors.white : AppColors.primary,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            child.name,
                            style: AppTextStyles.bodyText2.copyWith(
                              color: isSelected ? Colors.white : AppColors.textPrimary,
                              fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildTabBar() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.inputBackground,
        borderRadius: BorderRadius.circular(16),
      ),
      child: TabBar(
        controller: _tabController,
        indicator: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: AppColors.primary.withValues(alpha: 0.15),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        labelColor: AppColors.primary,
        unselectedLabelColor: AppColors.textTertiary,
        labelStyle: AppTextStyles.bodyText2.copyWith(
          fontWeight: FontWeight.w600,
          fontSize: 12,
        ),
        unselectedLabelStyle: AppTextStyles.bodyText2.copyWith(
          fontWeight: FontWeight.w500,
          fontSize: 12,
        ),
        dividerColor: Colors.transparent,
        splashBorderRadius: BorderRadius.circular(12),
        overlayColor: WidgetStateProperty.all(Colors.transparent),
        tabs: const [
          Tab(height: 40, child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text('📊'), SizedBox(width: 4), Text('概览'),
          ])),
          Tab(height: 40, child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text('📈'), SizedBox(width: 4), Text('成长'),
          ])),
          Tab(height: 40, child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text('🎯'), SizedBox(width: 4), Text('里程碑'),
          ])),
          Tab(height: 40, child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text('💉'), SizedBox(width: 4), Text('疫苗'),
          ])),
        ],
      ),
    );
  }

  Widget _buildContent() {
    if (_selectedChild == null) {
      return const Center(
        child: Text('请先选择一个宝宝'),
      );
    }

    return BlocBuilder<ChildGrowthBloc, ChildGrowthState>(
      builder: (context, state) {
        if (state is ChildGrowthLoading) {
          return const Center(child: CircularProgressIndicator());
        }

        if (state is ChildGrowthError) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, size: 48, color: AppColors.textTertiary),
                const SizedBox(height: 16),
                Text(state.message, style: AppTextStyles.bodyText2),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () {
                    if (_selectedChild != null) {
                      _loadChildData(_selectedChild!);
                    }
                  },
                  child: const Text('重试'),
                ),
              ],
            ),
          );
        }

        if (state is ChildGrowthLoaded) {
          return TabBarView(
            controller: _tabController,
            physics: const NeverScrollableScrollPhysics(),
            children: [
              _buildOverviewTab(state),
              _buildGrowthTab(state),
              _buildMilestonesTab(state),
              _buildVaccinesTab(state),
            ],
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildOverviewTab(ChildGrowthLoaded state) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 成长数据概览卡片
          GrowthSummaryCard(
            child: _selectedChild!,
            growthData: state.growthCurveData,
          ),
          const SizedBox(height: 20),

          // 待办提醒
          if (state.overdueVaccines.isNotEmpty || state.upcomingVaccines.isNotEmpty) ...[
            Text('待办提醒', style: AppTextStyles.subtitle1),
            const SizedBox(height: 12),
            ...[
              ...state.overdueVaccines.map((v) => _buildReminderCard(v, isOverdue: true)),
              ...state.upcomingVaccines.map((v) => _buildReminderCard(v)),
            ],
            const SizedBox(height: 20),
          ],

          // 快速入口
          Text('快速操作', style: AppTextStyles.subtitle1),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _buildQuickAction('📏', '记录身高', 1)),
              const SizedBox(width: 12),
              Expanded(child: _buildQuickAction('⚖️', '记录体重', 1)),
              const SizedBox(width: 12),
              Expanded(child: _buildQuickAction('🎯', '添加里程碑', 2)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildReminderCard(VaccineRecord vaccine, {bool isOverdue = false}) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isOverdue ? AppColors.error.withValues(alpha: 0.1) : AppColors.warning.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isOverdue ? AppColors.error.withValues(alpha: 0.3) : AppColors.warning.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        children: [
          Icon(
            isOverdue ? Icons.warning : Icons.schedule,
            color: isOverdue ? AppColors.error : AppColors.warning,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  vaccine.fullName,
                  style: AppTextStyles.bodyText1.copyWith(fontWeight: FontWeight.w600),
                ),
                Text(
                  isOverdue
                      ? '已过期 ${-vaccine.daysUntil} 天，请尽快接种'
                      : '${vaccine.daysUntilDisplay}接种',
                  style: AppTextStyles.caption.copyWith(
                    color: isOverdue ? AppColors.error : AppColors.warning,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickAction(String icon, String label, int tabIndex) {
    return GestureDetector(
      onTap: () {
        _tabController.animateTo(tabIndex);
        if (tabIndex == 1) {
          _showAddGrowthRecordSheet(context);
        } else if (tabIndex == 2) {
          _showAddMilestoneSheet(context);
        }
      },
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [AppColors.shadowLight],
        ),
        child: Column(
          children: [
            Text(icon, style: const TextStyle(fontSize: 24)),
            const SizedBox(height: 8),
            Text(label, style: AppTextStyles.caption),
          ],
        ),
      ),
    );
  }

  Widget _buildGrowthTab(ChildGrowthLoaded state) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 成长曲线图
          if (state.growthCurveData != null) ...[
            GrowthChart(data: state.growthCurveData!),
            const SizedBox(height: 20),
          ],

          // 历史记录
          Text('成长记录', style: AppTextStyles.subtitle1),
          const SizedBox(height: 12),
          if (state.growthCurveData?.records.isEmpty ?? true)
            _buildEmptyState('暂无成长记录', '点击下方按钮添加第一条记录')
          else
            ...state.growthCurveData!.records.map((record) => _buildGrowthRecordCard(record)),
        ],
      ),
    );
  }

  Widget _buildGrowthRecordCard(dynamic record) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.calendar_today, size: 16, color: AppColors.textSecondary),
              const SizedBox(width: 8),
              Text(
                _formatDate(record.recordDate),
                style: AppTextStyles.bodyText2.copyWith(fontWeight: FontWeight.w600),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              if (record.hasHeight) ...[
                _buildMeasurement('📏', '身高', record.heightDisplay),
                const SizedBox(width: 16),
              ],
              if (record.hasWeight) ...[
                _buildMeasurement('⚖️', '体重', record.weightDisplay),
                const SizedBox(width: 16),
              ],
              if (record.hasHeadCircumference)
                _buildMeasurement('🧠', '头围', record.headCircumferenceDisplay),
            ],
          ),
          if (record.notes?.isNotEmpty ?? false) ...[
            const SizedBox(height: 8),
            Text(
              record.notes!,
              style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMeasurement(String icon, String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(icon, style: const TextStyle(fontSize: 14)),
            const SizedBox(width: 4),
            Text(label, style: AppTextStyles.caption),
          ],
        ),
        Text(value, style: AppTextStyles.bodyText1.copyWith(fontWeight: FontWeight.w600)),
      ],
    );
  }

  Widget _buildMilestonesTab(ChildGrowthLoaded state) {
    return MilestoneTimeline(
      milestones: state.milestones,
      onAddMilestone: () => _showAddMilestoneSheet(context),
    );
  }

  Widget _buildVaccinesTab(ChildGrowthLoaded state) {
    return VaccineSchedule(
      vaccines: state.vaccines,
      onUpdateStatus: (vaccine, status) {
        context.read<ChildGrowthBloc>().add(
          VaccineStatusUpdateRequested(
            vaccineId: vaccine.id,
            status: status,
            actualDate: status == VaccineStatus.completed ? DateTime.now() : null,
          ),
        );
      },
    );
  }

  Widget _buildEmptyState(String title, String subtitle) {
    return Container(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.inbox_outlined, size: 48, color: AppColors.textTertiary),
          const SizedBox(height: 16),
          Text(title, style: AppTextStyles.subtitle1),
          const SizedBox(height: 8),
          Text(
            subtitle,
            style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  String _getAddButtonLabel() {
    switch (_tabController.index) {
      case 0:
      case 1:
        return '记录成长';
      case 2:
        return '添加里程碑';
      case 3:
        return '记录接种';
      default:
        return '添加';
    }
  }

  void _showAddDialog(BuildContext context) {
    switch (_tabController.index) {
      case 0:
      case 1:
        _showAddGrowthRecordSheet(context);
        break;
      case 2:
        _showAddMilestoneSheet(context);
        break;
      case 3:
        // TODO: 显示接种记录表单
        break;
    }
  }

  void _showAddGrowthRecordSheet(BuildContext context) {
    if (_selectedChild == null) return;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => BlocProvider.value(
        value: context.read<ChildGrowthBloc>(),
        child: AddGrowthRecordSheet(
          childId: _selectedChild!.id,
          childName: _selectedChild!.name,
        ),
      ),
    );
  }

  void _showAddMilestoneSheet(BuildContext context) {
    if (_selectedChild == null) return;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => BlocProvider.value(
        value: context.read<ChildGrowthBloc>(),
        child: AddMilestoneSheet(
          childId: _selectedChild!.id,
          childName: _selectedChild!.name,
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }
}
