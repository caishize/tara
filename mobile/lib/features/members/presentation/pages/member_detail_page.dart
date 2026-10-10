import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:get_it/get_it.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/member.dart';
import '../../data/datasources/member_remote_datasource.dart';
import '../../data/models/work_history_model.dart';
import '../../data/models/member_model.dart';
import '../../data/models/member_insight_model.dart';
import '../../data/models/professional_relation_model.dart';
import '../../../kanban/data/models/insight_feed_models.dart';
import '../../../kanban/domain/repositories/insight_feed_repository.dart';
import '../../../kanban/presentation/widgets/insight_section.dart';
import '../bloc/members_bloc.dart';
import '../widgets/location_edit_dialog.dart';

class MemberDetailPage extends StatefulWidget {
  final String memberId;

  const MemberDetailPage({super.key, required this.memberId});

  @override
  State<MemberDetailPage> createState() => _MemberDetailPageState();
}

class _MemberDetailPageState extends State<MemberDetailPage> {
  late final MemberRemoteDataSource _dataSource;
  List<WorkHistoryModel> _workHistory = [];
  List<ProfessionalRelationModel> _professionalRelations = [];
  List<MemberInsightModel> _memberInsights = [];
  bool _isLoadingExtra = false;

  @override
  void initState() {
    super.initState();
    _dataSource = GetIt.instance<MemberRemoteDataSource>();
    // Load members if not already loaded
    final state = context.read<MembersBloc>().state;
    if (state is! MembersLoaded) {
      context.read<MembersBloc>().add(const MembersLoadRequested());
    }
    _loadExtraData();
  }

  Future<void> _loadExtraData() async {
    if (!mounted) return;
    setState(() => _isLoadingExtra = true);
    try {
      final workHistoryFuture = _dataSource.getWorkHistory(widget.memberId);
      final relationsForture = _dataSource.getProfessionalRelations(widget.memberId);
      final insightsFuture = _dataSource.getMemberInsights(widget.memberId);

      final workHistory = await workHistoryFuture;
      final relations = await relationsForture;
      final insights = await insightsFuture;

      if (!mounted) return;
      setState(() {
        _workHistory = workHistory;
        _professionalRelations = relations;
        _memberInsights = insights;
        _isLoadingExtra = false;
      });
    } catch (e) {
      debugPrint('Error loading extra data: $e');
      if (!mounted) return;
      setState(() => _isLoadingExtra = false);
    }
  }

  void _handleInsightAction(
    InsightFeedItemModel insight,
    String actionType,
    Map<String, dynamic>? payload,
  ) {
    switch (actionType) {
      case 'open_chat':
        // Navigate to conversation with pre-filled context
        context.push(Routes.conversation);
        break;

      case 'create_pending_action':
        _executeInsightAction(insight, actionType, payload);
        break;

      case 'adopt':
        final tripId = payload?['related_trip_id'] as String?;
        if (tripId != null && tripId.isNotEmpty) {
          _adoptInsightToTrip(insight, tripId);
        } else {
          _executeInsightAction(insight, actionType, payload);
        }
        break;

      case 'confirm_pending_action':
        final paId = payload?['pending_action_id'] as String?;
        if (paId != null) {
          _confirmPendingAction(paId);
        }
        break;

      case 'open_detail':
        // Default tap behavior already opens detail sheet
        break;

      default:
        // Fallback: execute as generic insight action
        _executeInsightAction(insight, actionType, payload);
        break;
    }
  }

  Future<void> _executeInsightAction(
    InsightFeedItemModel insight,
    String actionType,
    Map<String, dynamic>? payload,
  ) async {
    try {
      final repository = GetIt.instance<InsightFeedRepository>();
      final result = await repository.executeInsightAction(
        insightId: insight.id,
        actionType: actionType,
        actionData: payload,
      );
      result.fold(
        (failure) => debugPrint('Insight action failed: $failure'),
        (pendingAction) {
          if (!mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(pendingAction.displayTitle.isNotEmpty
                  ? pendingAction.displayTitle
                  : '操作已创建'),
              behavior: SnackBarBehavior.floating,
            ),
          );
          _loadExtraData();
        },
      );
    } catch (e) {
      debugPrint('Error executing insight action: $e');
    }
  }

  Future<void> _adoptInsightToTrip(
    InsightFeedItemModel insight,
    String tripId,
  ) async {
    try {
      final repository = GetIt.instance<InsightFeedRepository>();
      await repository.adoptInsight(
        insightId: insight.id,
        tripId: tripId,
      );
      _loadExtraData();
    } catch (e) {
      debugPrint('Error adopting insight: $e');
    }
  }

  Future<void> _confirmPendingAction(String actionId) async {
    try {
      final repository = GetIt.instance<InsightFeedRepository>();
      await repository.confirmAction(actionId: actionId);
      _loadExtraData();
    } catch (e) {
      debugPrint('Error confirming action: $e');
    }
  }

  Future<bool> _handleInsightDismiss(InsightFeedItemModel insight) async {
    try {
      final repository = GetIt.instance<InsightFeedRepository>();
      await repository.submitInsightFeedback(
        insightId: insight.id,
        feedbackType: 'not_useful',
      );
      setState(() {
        _memberInsights = _memberInsights.where((i) => i.id != insight.id).toList();
      });
      return true;
    } catch (e) {
      debugPrint('Error dismissing insight: $e');
      return false;
    }
  }

  Member? _findMember(List<Member> members) {
    try {
      return members.firstWhere((m) => m.id == widget.memberId);
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<MembersBloc, MembersState>(
      listener: (context, state) {
        // When member is deleted, pop back to members list
        if (state is MemberDeleteSuccess && state.memberId == widget.memberId) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('成员已删除')),
            );
            context.pop();
          }
        }
      },
      child: Scaffold(
        backgroundColor: AppColors.background,
        body: BlocBuilder<MembersBloc, MembersState>(
          builder: (context, state) {
            if (state is MembersLoading) {
              return const Center(child: CircularProgressIndicator());
            }

            if (state is MembersLoaded) {
              final member = _findMember(state.members);
              if (member == null) {
                return _buildNotFound();
              }
              return _buildContent(member);
            }

            if (state is MembersError) {
              return _buildError(state.message);
            }

            return const Center(child: CircularProgressIndicator());
          },
        ),
      ),
    );
  }

  Widget _buildNotFound() {
    return CustomScrollView(
      slivers: [
        _buildAppBar(null),
        SliverFillRemaining(
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.person_off_outlined, size: 64, color: AppColors.textTertiary),
                const SizedBox(height: 16),
                Text('未找到该成员', style: AppTextStyles.subtitle1),
                const SizedBox(height: 8),
                Text(
                  '成员可能已被删除',
                  style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: () => context.pop(),
                  child: const Text('返回'),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildError(String message) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48, color: AppColors.error),
          const SizedBox(height: 16),
          Text(message, style: AppTextStyles.bodyText2),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () {
              context.read<MembersBloc>().add(const MembersLoadRequested());
            },
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  Widget _buildContent(Member member) {
    return CustomScrollView(
      slivers: [
        _buildAppBar(member),
        SliverToBoxAdapter(child: _buildProfileHeader(member)),
        SliverToBoxAdapter(child: _buildInfoSection(member)),
        SliverToBoxAdapter(child: _buildInsightsSection(member)),
        SliverToBoxAdapter(child: _buildWorkHistorySection(member)),
        SliverToBoxAdapter(child: _buildProfessionalRelationsSection(member)),
        SliverToBoxAdapter(child: _buildLocationSection(member)),
        SliverToBoxAdapter(child: _buildPreferencesSection(member)),
        SliverToBoxAdapter(child: _buildProfileSection(member)),
        SliverToBoxAdapter(child: _buildHealthSection(member)),
        SliverToBoxAdapter(child: _buildActionsSection(member)),
        const SliverPadding(padding: EdgeInsets.only(bottom: 100)),
      ],
    );
  }

  Widget _buildAppBar(Member? member) {
    return SliverAppBar(
      expandedHeight: 60,
      floating: true,
      pinned: true,
      backgroundColor: AppColors.background,
      foregroundColor: AppColors.textPrimary,
      elevation: 0,
      leading: IconButton(
        icon: const Icon(Icons.arrow_back_ios),
        onPressed: () => context.pop(),
      ),
      title: Text(member?.name ?? '成员详情', style: AppTextStyles.headline6),
      centerTitle: true,
      actions: [
        if (member != null) ...[
          IconButton(
            icon: const Icon(Icons.edit_outlined),
            onPressed: () {
              context.push('/members/edit/${member.id}');
            },
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert),
            onSelected: (value) {
              if (value == 'delete') {
                _showDeleteConfirmation(member);
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'delete',
                child: Row(
                  children: [
                    Icon(Icons.delete_outline, color: Colors.red, size: 20),
                    SizedBox(width: 8),
                    Text('删除', style: TextStyle(color: Colors.red)),
                  ],
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  void _showDeleteConfirmation(Member member) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认删除'),
        content: Text('确定要删除 ${member.name} 吗？此操作无法撤销。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(ctx).pop(); // Close dialog
              // Trigger delete - BlocListener will handle navigation after success
              context.read<MembersBloc>().add(MemberDeleteRequested(memberId: member.id));
            },
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }

  Widget _buildProfileHeader(Member member) {
    return Container(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          // Avatar
          Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: AppColors.primary.withValues(alpha: 0.3),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Center(
              child: Text(
                member.name.isNotEmpty ? member.name[0].toUpperCase() : '?',
                style: const TextStyle(
                  fontSize: 40,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          // Name
          Text(member.name, style: AppTextStyles.headline4),
          if (member.nickname != null && member.nickname!.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              member.nickname!,
              style: AppTextStyles.bodyText1.copyWith(color: AppColors.textSecondary),
            ),
          ],
          const SizedBox(height: 8),
          // Relation badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              member.relationText,
              style: AppTextStyles.bodyText2.copyWith(
                color: AppColors.primary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(height: 16),
          // Profile completion
          _buildProfileCompletion(member.profileCompletion),
        ],
      ),
    );
  }

  Widget _buildProfileCompletion(int completion) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('资料完整度', style: AppTextStyles.bodyText2),
              Text(
                '$completion%',
                style: AppTextStyles.subtitle1.copyWith(
                  color: completion >= 80 ? AppColors.success : AppColors.warning,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: completion / 100,
              backgroundColor: AppColors.divider,
              valueColor: AlwaysStoppedAnimation<Color>(
                completion >= 80 ? AppColors.success : AppColors.warning,
              ),
              minHeight: 6,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoSection(Member member) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          Text('基本信息', style: AppTextStyles.headline6),
          const SizedBox(height: 12),
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [AppColors.shadowLight],
            ),
            child: Column(
              children: [
                _buildInfoItem(Icons.cake_outlined, '生日', member.birthDate ?? '未设置'),
                _buildInfoDivider(),
                _buildInfoItem(Icons.person_outline, '性别', member.genderText ?? '未设置'),
                _buildInfoDivider(),
                _buildInfoItem(Icons.numbers, '年龄', member.age != null ? '${member.age}岁' : '未知'),
                _buildInfoDivider(),
                _buildInfoItem(Icons.phone_outlined, '电话', member.phone ?? '未设置'),
                _buildInfoDivider(),
                _buildInfoItem(Icons.email_outlined, '邮箱', member.email ?? '未设置'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoItem(IconData icon, String label, String value) {
    final isSet = value != '未设置' && value != '未知';
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: AppColors.primary, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary)),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: AppTextStyles.bodyText1.copyWith(
                    color: isSet ? AppColors.textPrimary : AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          ),
          if (!isSet)
            TextButton(
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: const Text('编辑功能即将上线'),
                    behavior: SnackBarBehavior.floating,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                );
              },
              child: const Text('设置'),
            ),
        ],
      ),
    );
  }

  Widget _buildInfoDivider() {
    return Divider(height: 1, indent: 68, color: AppColors.divider.withValues(alpha: 0.5));
  }

  // ==========================================================================
  // Insights Section
  // ==========================================================================

  Widget _buildInsightsSection(Member member) {
    if (_memberInsights.isEmpty) return const SizedBox.shrink();

    final unifiedInsights = _memberInsights
        .map((m) => m.toInsightFeedItem())
        .toList();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          InsightSection(
            insights: unifiedInsights,
            title: 'AI \u6D1E\u5BDF',
            icon: Icons.lightbulb_outline,
            maxVisible: 5,
            showActions: true,
            onInsightActionTap: _handleInsightAction,
            onInsightDismiss: _handleInsightDismiss,
          ),
        ],
      ),
    );
  }

  Widget _buildWorkHistorySection(Member member) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('工作履历', style: AppTextStyles.headline6),
              TextButton.icon(
                onPressed: () async {
                  final result = await context.push<bool>(
                    '/members/${member.id}/work-history/add',
                  );
                  if (result == true) _loadExtraData();
                },
                icon: const Icon(Icons.add, size: 18),
                label: const Text('添加'),
                style: TextButton.styleFrom(
                  foregroundColor: AppColors.primary,
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_isLoadingExtra)
            const Center(child: CircularProgressIndicator())
          else if (_workHistory.isEmpty)
            _buildEmptyCard(
              icon: Icons.work_outline,
              message: '暂无工作履历',
              onAdd: () async {
                final result = await context.push<bool>(
                  '/members/${member.id}/work-history/add',
                );
                if (result == true) _loadExtraData();
              },
            )
          else
            Column(
              children: _workHistory.map((wh) => _buildWorkHistoryCard(wh, member)).toList(),
            ),
        ],
      ),
    );
  }

  Widget _buildWorkHistoryCard(WorkHistoryModel workHistory, Member member) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () async {
            final result = await context.push<bool>(
              '/members/${member.id}/work-history/${workHistory.id}/edit',
            );
            if (result == true) _loadExtraData();
          },
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: workHistory.isCurrent
                        ? AppColors.success.withValues(alpha: 0.1)
                        : AppColors.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    Icons.business,
                    color: workHistory.isCurrent ? AppColors.success : AppColors.primary,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              workHistory.companyName,
                              style: AppTextStyles.subtitle1,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (workHistory.isCurrent)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppColors.success.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                '在职',
                                style: AppTextStyles.caption.copyWith(
                                  color: AppColors.success,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                        ],
                      ),
                      if (workHistory.position != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          workHistory.position!,
                          style: AppTextStyles.bodyText2.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                      const SizedBox(height: 4),
                      Text(
                        workHistory.periodText,
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textTertiary,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: AppColors.textTertiary),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildProfessionalRelationsSection(Member member) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('职业关系', style: AppTextStyles.headline6),
              TextButton.icon(
                onPressed: () async {
                  final result = await context.push<bool>(
                    '/members/${member.id}/professional-relations/add',
                  );
                  if (result == true) _loadExtraData();
                },
                icon: const Icon(Icons.add, size: 18),
                label: const Text('添加'),
                style: TextButton.styleFrom(
                  foregroundColor: AppColors.primary,
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_isLoadingExtra)
            const Center(child: CircularProgressIndicator())
          else if (_professionalRelations.isEmpty)
            _buildEmptyCard(
              icon: Icons.people_outline,
              message: '暂无职业关系',
              onAdd: () async {
                final result = await context.push<bool>(
                  '/members/${member.id}/professional-relations/add',
                );
                if (result == true) _loadExtraData();
              },
            )
          else
            Column(
              children: _professionalRelations
                  .map((pr) => _buildProfessionalRelationCard(pr, member))
                  .toList(),
            ),
        ],
      ),
    );
  }

  Widget _buildProfessionalRelationCard(ProfessionalRelationModel relation, Member member) {
    // Determine the other person's name and display text based on perspective
    final otherName = relation.fromMemberId == member.id
        ? relation.toMemberName
        : relation.fromMemberName;
    // Get display text with perspective inversion
    final relationDisplayText = relation.getDisplayTextForMember(member.id);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () async {
            final result = await context.push<bool>(
              '/members/${member.id}/professional-relations/${relation.id}/edit',
            );
            if (result == true) _loadExtraData();
          },
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: relation.isCurrent
                        ? AppColors.secondary.withValues(alpha: 0.1)
                        : AppColors.textTertiary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    _getRelationIcon(relation.relationType),
                    color: relation.isCurrent ? AppColors.secondary : AppColors.textTertiary,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              otherName ?? '未知',
                              style: AppTextStyles.subtitle1,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: relation.isCurrent
                                  ? AppColors.secondary.withValues(alpha: 0.1)
                                  : AppColors.textTertiary.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              relationDisplayText,
                              style: AppTextStyles.caption.copyWith(
                                color: relation.isCurrent
                                    ? AppColors.secondary
                                    : AppColors.textTertiary,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                      if (relation.companyName != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          '@ ${relation.companyName}',
                          style: AppTextStyles.bodyText2.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                      if (relation.notes != null && relation.notes!.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          relation.notes!,
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.textTertiary,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: AppColors.textTertiary),
              ],
            ),
          ),
        ),
      ),
    );
  }

  IconData _getRelationIcon(String relationType) {
    switch (relationType) {
      case 'boss':
        return Icons.supervisor_account;
      case 'subordinate':
        return Icons.person_outline;
      case 'peer':
        return Icons.people;
      case 'mentor':
        return Icons.school;
      case 'mentee':
        return Icons.person_pin;
      case 'client':
        return Icons.handshake;
      case 'vendor':
        return Icons.store;
      case 'partner':
        return Icons.business_center;
      default:
        return Icons.person;
    }
  }

  Widget _buildEmptyCard({
    required IconData icon,
    required String message,
    required VoidCallback onAdd,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onAdd,
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Center(
              child: Column(
                children: [
                  Icon(icon, size: 40, color: AppColors.textTertiary),
                  const SizedBox(height: 8),
                  Text(
                    message,
                    style: AppTextStyles.bodyText2.copyWith(color: AppColors.textTertiary),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '点击添加',
                    style: AppTextStyles.caption.copyWith(color: AppColors.primary),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLocationSection(Member member) {
    final locations = member.locations;
    final hasLocations = locations != null && locations.isNotEmpty;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('常用地址', style: AppTextStyles.headline6),
              TextButton.icon(
                onPressed: () => _showLocationEditDialog(member, null, null),
                icon: const Icon(Icons.add, size: 18),
                label: const Text('添加'),
                style: TextButton.styleFrom(
                  foregroundColor: AppColors.primary,
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [AppColors.shadowLight],
            ),
            child: hasLocations
                ? Column(
                    children: locations.entries.map((entry) {
                      final locationType = entry.key;
                      final locationData = entry.value as Map<String, dynamic>?;
                      final address = locationData?['address'] ?? '未设置';
                      return _buildLocationItem(member, locationType, address);
                    }).toList(),
                  )
                : GestureDetector(
                    onTap: () => _showLocationEditDialog(member, null, null),
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Center(
                        child: Column(
                          children: [
                            const Icon(Icons.location_off_outlined, size: 40, color: AppColors.textTertiary),
                            const SizedBox(height: 8),
                            Text(
                              '暂无地址信息',
                              style: AppTextStyles.bodyText2.copyWith(color: AppColors.textTertiary),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '点击添加',
                              style: AppTextStyles.caption.copyWith(color: AppColors.primary),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildLocationItem(Member member, String type, String address) {
    final icon = type == 'home' ? Icons.home_outlined : Icons.work_outlined;
    final label = type == 'home' ? '家庭住址' : '工作地址';

    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: () => _showLocationEditDialog(member, type, address),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.secondary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: AppColors.secondary, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary)),
                  const SizedBox(height: 2),
                  Text(address, style: AppTextStyles.bodyText1),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: AppColors.textTertiary, size: 20),
          ],
        ),
      ),
    );
  }

  void _showLocationEditDialog(Member member, String? existingType, String? existingAddress) async {
    final result = await showLocationEditDialog(
      context: context,
      existingType: existingType,
      existingAddress: existingAddress,
      existingLocationTypes: member.locations?.keys.toSet() ?? {},
    );

    if (result == null || !mounted) return;

    final updatedLocations = Map<String, dynamic>.from(member.locations ?? {});

    if (result.isDelete) {
      // Delete the location
      if (existingType != null) {
        updatedLocations.remove(existingType);
      }
    } else {
      // Add or update
      // If type changed, remove old key
      if (existingType != null && existingType != result.type) {
        updatedLocations.remove(existingType);
      }
      updatedLocations[result.type] = {'address': result.address};
    }

    final updatedMember = MemberModel(
      id: member.id,
      name: member.name,
      nickname: member.nickname,
      gender: member.gender,
      birthDate: member.birthDate,
      age: member.age,
      phone: member.phone,
      email: member.email,
      idCard: member.idCard,
      relation: member.relation,
      profileCompletion: member.profileCompletion,
      locations: updatedLocations.isEmpty ? null : updatedLocations,
      defaultLocationType: member.defaultLocationType,
      profile: member.profile,
      preferences: member.preferences,
      healthInfo: member.healthInfo,
      currentCompany: member.currentCompany,
      currentPosition: member.currentPosition,
    );

    context.read<MembersBloc>().add(MemberUpdateRequested(updatedMember));
  }

  Widget _buildPreferencesSection(Member member) {
    final prefs = member.preferences;
    if (prefs == null ||
        (prefs.giftPreferences?.isEmpty ?? true) &&
            (prefs.avoidItems?.isEmpty ?? true)) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          Text('偏好设置', style: AppTextStyles.headline6),
          const SizedBox(height: 12),
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [AppColors.shadowLight],
            ),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (prefs.giftPreferences?.isNotEmpty ?? false) ...[
                  Text('礼物偏好', style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: prefs.giftPreferences!.map((pref) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppColors.success.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Text(pref, style: AppTextStyles.caption.copyWith(color: AppColors.success)),
                    )).toList(),
                  ),
                  const SizedBox(height: 16),
                ],
                if (prefs.avoidItems?.isNotEmpty ?? false) ...[
                  Text('不喜欢的物品', style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: prefs.avoidItems!.map((item) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppColors.error.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Text(item, style: AppTextStyles.caption.copyWith(color: AppColors.error)),
                    )).toList(),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProfileSection(Member member) {
    final profile = member.profile;
    if (profile == null ||
        (profile.occupation == null &&
            profile.education == null &&
            (profile.hobbies?.isEmpty ?? true) &&
            profile.personality == null)) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          Text('个人档案', style: AppTextStyles.headline6),
          const SizedBox(height: 12),
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [AppColors.shadowLight],
            ),
            child: Column(
              children: [
                if (profile.occupation != null)
                  _buildInfoItem(Icons.work_outline, '职业', profile.occupation!),
                if (profile.occupation != null && profile.education != null)
                  _buildInfoDivider(),
                if (profile.education != null)
                  _buildInfoItem(Icons.school_outlined, '学历', profile.education!),
                if ((profile.occupation != null || profile.education != null) &&
                    (profile.hobbies?.isNotEmpty ?? false))
                  _buildInfoDivider(),
                if (profile.hobbies?.isNotEmpty ?? false)
                  _buildInfoItem(Icons.favorite_outline, '爱好', profile.hobbies!.join('、')),
                if (profile.personality != null) ...[
                  _buildInfoDivider(),
                  _buildInfoItem(Icons.psychology_outlined, '性格', profile.personality!),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHealthSection(Member member) {
    final health = member.healthInfo;
    if (health == null ||
        (health.bloodType == null &&
            (health.allergies?.isEmpty ?? true) &&
            (health.chronicConditions?.isEmpty ?? true))) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          Text('健康信息', style: AppTextStyles.headline6),
          const SizedBox(height: 12),
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [AppColors.shadowLight],
            ),
            child: Column(
              children: [
                if (health.bloodType != null)
                  _buildInfoItem(Icons.bloodtype_outlined, '血型', health.bloodType!),
                if (health.bloodType != null && (health.allergies?.isNotEmpty ?? false))
                  _buildInfoDivider(),
                if (health.allergies?.isNotEmpty ?? false)
                  _buildInfoItem(Icons.warning_amber_outlined, '过敏源', health.allergies!.join('、')),
                if ((health.allergies?.isNotEmpty ?? false) &&
                    (health.chronicConditions?.isNotEmpty ?? false))
                  _buildInfoDivider(),
                if (health.chronicConditions?.isNotEmpty ?? false)
                  _buildInfoItem(Icons.healing_outlined, '慢性病', health.chronicConditions!.join('、')),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionsSection(Member member) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 4),
          Text('快捷操作', style: AppTextStyles.headline6),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _buildActionButton(
                  icon: Icons.card_giftcard,
                  label: '推荐礼物',
                  color: AppColors.accent1,
                  onTap: () {
                    context.push('/discover/recommend/${member.id}');
                  },
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildActionButton(
                  icon: Icons.event,
                  label: '添加日期',
                  color: AppColors.secondary,
                  onTap: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: const Text('添加日期功能即将上线'),
                        behavior: SnackBarBehavior.floating,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 20),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            boxShadow: [AppColors.shadowLight],
          ),
          child: Column(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(height: 8),
              Text(
                label,
                style: AppTextStyles.bodyText2.copyWith(fontWeight: FontWeight.w600),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
