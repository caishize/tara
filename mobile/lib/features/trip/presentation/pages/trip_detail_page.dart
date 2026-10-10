import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../shared/utils/relation_utils.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../chat/presentation/bloc/assistant_bloc.dart';
import '../../../members/data/datasources/member_remote_datasource.dart';
import '../../../members/data/models/member_model.dart';
import '../../domain/entities/trip.dart';
import '../bloc/trip_bloc.dart';
import '../widgets/trip_hero_card.dart';
import '../widgets/trip_overview_tab.dart';
import '../widgets/trip_schedule_tab.dart';

/// Trip Detail V2 — green gradient hero + overview/schedule tabs.
class TripDetailPage extends StatefulWidget {
  final String tripId;

  const TripDetailPage({super.key, required this.tripId});

  @override
  State<TripDetailPage> createState() => _TripDetailPageState();
}

class _TripDetailPageState extends State<TripDetailPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadPlanDetails();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _loadPlanDetails() {
    context.read<TripBloc>().add(TripLoadRequested(widget.tripId));
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<TripBloc, TripState>(
      listenWhen: (previous, current) {
        return current is TripOperationSuccess || current is TripError;
      },
      listener: (context, state) {
        if (state is TripOperationSuccess) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(state.message)),
          );
          if (state.message.contains('\u5220\u9664')) {
            context.pop(true);
          } else {
            _loadPlanDetails();
          }
        } else if (state is TripError) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(state.message),
              backgroundColor: AppColors.error,
              duration: const Duration(seconds: 4),
            ),
          );
        }
      },
      buildWhen: (previous, current) {
        return current is TripDetailLoaded;
      },
      builder: (context, state) {
        if (state is TripDetailLoaded) {
          return _buildContent(context, state);
        }

        return Scaffold(
          backgroundColor: AppColors.background,
          appBar: AppBar(
            title: const Text('\u884C\u7A0B\u8BE6\u60C5'),
            backgroundColor: AppColors.background,
            elevation: 0,
          ),
          body: const Center(child: CircularProgressIndicator()),
        );
      },
    );
  }

  Widget _buildContent(BuildContext context, TripDetailLoaded state) {
    final plan = state.plan;

    // Get current user ID to filter self from participants
    String? currentUserId;
    try {
      final authState = context.read<AuthBloc>().state;
      if (authState is AuthAuthenticated) {
        currentUserId = authState.user.id;
      }
    } catch (_) {
      // AuthBloc might not be in context
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Column(
        children: [
          // Status bar spacer
          SizedBox(height: MediaQuery.of(context).padding.top),

          // Flat header: ← "行程详情" + ··· menu
          _buildFlatHeader(context, plan),

          // Hero card
          TripHeroCard(trip: plan),

          // Tab bar
          _buildTabBar(),

          // Tab content
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                TripOverviewTab(
                  trip: plan,
                  itinerary: state.itinerary,
                  budgetStatus: state.budgetStatus,
                  tripContext: state.tripContext,
                  associations: state.associations,
                  relatedMemories: state.relatedMemories,
                  currentUserId: currentUserId,
                  onChatContinue: () => _continueInChat(
                    context,
                    plan,
                    pendingPrepItems: state.tripContext?.preparationItems
                            .where((item) => !item.done)
                            .take(2)
                            .map((item) => item.text)
                            .toList() ??
                        const [],
                  ),
                  onManageParticipants: () =>
                      _manageParticipants(context, state),
                  onTogglePrepItem: (curatedEventId, itemKey, done) {
                    context.read<TripBloc>().add(
                          TripPrepItemToggleRequested(
                            tripId: widget.tripId,
                            curatedEventId: curatedEventId,
                            itemKey: itemKey,
                            done: done,
                          ),
                        );
                  },
                ),
                TripScheduleTab(
                  trip: plan,
                  itinerary: state.itinerary,
                  onAdjustSchedule: () => _continueInChat(context, plan),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFlatHeader(BuildContext context, Trip plan) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: SizedBox(
        height: 48,
        child: Row(
          children: [
            IconButton(
              onPressed: () => context.pop(),
              icon: const Icon(
                Icons.arrow_back,
                color: AppColors.textPrimary,
              ),
            ),
            const Text(
              '\u884C\u7A0B\u8BE6\u60C5',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
            const Spacer(),
            PopupMenuButton<String>(
              onSelected: (value) {
                switch (value) {
                  case 'edit':
                    context.push('/trips/${widget.tripId}/edit');
                    break;
                  case 'expense':
                    context.push('/trips/${widget.tripId}/expense/add');
                    break;
                  case 'delete':
                    _showDeleteConfirmation(context);
                    break;
                }
              },
              icon: const Icon(
                Icons.more_horiz,
                color: AppColors.textSecondary,
              ),
              itemBuilder: (context) => [
                const PopupMenuItem(
                  value: 'edit',
                  child: Row(
                    children: [
                      Icon(Icons.edit_outlined, size: 18),
                      SizedBox(width: 8),
                      Text('\u7F16\u8F91'),
                    ],
                  ),
                ),
                const PopupMenuItem(
                  value: 'expense',
                  child: Row(
                    children: [
                      Icon(Icons.receipt_long_outlined, size: 18),
                      SizedBox(width: 8),
                      Text('\u8BB0\u5F55\u652F\u51FA'),
                    ],
                  ),
                ),
                const PopupMenuItem(
                  value: 'delete',
                  child: Row(
                    children: [
                      Icon(Icons.delete_outline, size: 18, color: Colors.red),
                      SizedBox(width: 8),
                      Text('\u5220\u9664', style: TextStyle(color: Colors.red)),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTabBar() {
    return Container(
      decoration: const BoxDecoration(
        border: Border(
          bottom: BorderSide(color: AppColors.divider, width: 1),
        ),
      ),
      child: TabBar(
        controller: _tabController,
        labelColor: AppColors.accentGreen,
        unselectedLabelColor: AppColors.textTertiary,
        indicatorColor: AppColors.accentGreen,
        indicatorWeight: 3,
        labelStyle: const TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w700,
        ),
        unselectedLabelStyle: const TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w500,
        ),
        tabs: const [
          Tab(text: '\u6982\u89C8'),
          Tab(text: '\u65E5\u7A0B'),
        ],
      ),
    );
  }

  void _continueInChat(
    BuildContext context,
    Trip plan, {
    List<String> pendingPrepItems = const [],
  }) {
    final destination = plan.destination;
    final dateRange =
        '${plan.startDate.month}/${plan.startDate.day}-${plan.endDate.month}/${plan.endDate.day}';
    final prefix =
        '\u5173\u4E8E\u6211\u7684$destination\u884C\u7A0B($dateRange)';
    final prepHint = pendingPrepItems.isNotEmpty
        ? '\u5F53\u524D\u672A\u5B8C\u6210\u51C6\u5907\u9879\uFF1A${pendingPrepItems.join('\uFF1B')}'
        : null;
    final prompt = prepHint != null
        ? '$prefix\uFF0C$prepHint\u3002\u8BF7\u7ED9\u6211\u4E0B\u4E00\u6B65\u5177\u4F53\u53EF\u6267\u884C\u64CD\u4F5C\u3002'
        : '$prefix\uFF0C\u5E2E\u6211\u770B\u770B\u8FD8\u6709\u4EC0\u4E48\u9700\u8981\u51C6\u5907\u7684';

    context.read<AssistantBloc>().add(
          AssistantStreamMessage(prompt),
        );
    context.go('/conversation');
  }

  void _showDeleteConfirmation(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('\u786E\u8BA4\u5220\u9664'),
        content: const Text(
            '\u786E\u5B9A\u8981\u5220\u9664\u8FD9\u4E2A\u65C5\u884C\u8BA1\u5212\u5417\uFF1F\u6B64\u64CD\u4F5C\u4E0D\u53EF\u6062\u590D\u3002'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('\u53D6\u6D88'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              context.read<TripBloc>().add(
                    TripDeleteRequested(widget.tripId),
                  );
            },
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('\u5220\u9664'),
          ),
        ],
      ),
    );
  }

  Future<void> _manageParticipants(
    BuildContext context,
    TripDetailLoaded state,
  ) async {
    final initial = <String>{
      ...state.plan.participants,
      ...?state.tripContext?.participants.map((p) => p.id),
    };

    final selected = await _showParticipantPicker(context, initial);
    if (!context.mounted || selected == null) {
      return;
    }

    if (selected.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('至少保留 1 位参与成员')),
      );
      return;
    }

    final hasChanged =
        selected.length != initial.length || !selected.containsAll(initial);
    if (!hasChanged) {
      return;
    }

    context.read<TripBloc>().add(
          TripUpdateRequested(
            state.plan.id,
            state.plan.copyWith(participants: selected.toList()),
          ),
        );
  }

  Future<Set<String>?> _showParticipantPicker(
    BuildContext context,
    Set<String> initialSelected,
  ) async {
    List<MemberModel> members;
    try {
      members = await getIt<MemberRemoteDataSource>().getMembers();
    } catch (_) {
      if (!context.mounted) return null;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('加载家庭成员失败，请稍后重试')),
      );
      return null;
    }

    if (!context.mounted) return null;
    if (members.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('当前家庭还没有成员可添加')),
      );
      return null;
    }

    final memberIdSet = members.map((m) => m.id).toSet();
    final selected = <String>{
      ...initialSelected.where(memberIdSet.contains),
    };
    if (selected.isEmpty) {
      selected.add(members.first.id);
    }

    return showModalBottomSheet<Set<String>>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final bottomInset = MediaQuery.of(context).viewInsets.bottom;
            return SafeArea(
              child: Padding(
                padding: EdgeInsets.only(bottom: bottomInset),
                child: SizedBox(
                  height: MediaQuery.of(context).size.height * 0.75,
                  child: Column(
                    children: [
                      const SizedBox(height: 12),
                      const Text(
                        '编辑参与成员',
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '已选择 ${selected.length} 位',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Expanded(
                        child: ListView.separated(
                          itemCount: members.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, index) {
                            final member = members[index];
                            final displayName =
                                member.nickname?.isNotEmpty == true
                                    ? member.nickname!
                                    : member.name;
                            final metaParts = <String>[];
                            if (member.relation.isNotEmpty) {
                              metaParts.add(
                                RelationUtils.getRelationLabel(member.relation),
                              );
                            }
                            if (member.age != null) {
                              metaParts.add('${member.age}岁');
                            }
                            final meta = metaParts.join(' · ');
                            final checked = selected.contains(member.id);

                            return CheckboxListTile(
                              value: checked,
                              onChanged: (value) {
                                setSheetState(() {
                                  if (value == true) {
                                    selected.add(member.id);
                                  } else {
                                    selected.remove(member.id);
                                  }
                                });
                              },
                              title: Text(displayName),
                              subtitle: meta.isEmpty ? null : Text(meta),
                              controlAffinity: ListTileControlAffinity.leading,
                              activeColor: AppColors.accentGreen,
                            );
                          },
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                        child: Row(
                          children: [
                            Expanded(
                              child: OutlinedButton(
                                onPressed: () => Navigator.pop(sheetContext),
                                child: const Text('取消'),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: ElevatedButton(
                                onPressed: () => Navigator.pop(
                                  sheetContext,
                                  Set<String>.from(selected),
                                ),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppColors.accentGreen,
                                  foregroundColor: Colors.white,
                                ),
                                child: const Text('保存'),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}
