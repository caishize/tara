import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../members/data/datasources/member_remote_datasource.dart';
import '../../../members/domain/entities/member.dart';
import '../../data/datasources/relationship_remote_datasource.dart';
import '../bloc/favor_ledger_bloc.dart';

/// Favor Ledger page for managing 人情账本 with light theme
class FavorLedgerPage extends StatelessWidget {
  const FavorLedgerPage({super.key});

  @override
  Widget build(BuildContext context) {
    // Get familyId from auth context
    final authState = context.read<AuthBloc>().state;
    final familyId = authState is AuthAuthenticated ? authState.user.familyId : '';

    return BlocProvider(
      create: (context) => FavorLedgerBloc(
        dataSource: getIt<RelationshipRemoteDataSource>(),
        memberDataSource: getIt<MemberRemoteDataSource>(),
      )..add(FavorLedgerLoadRequested(familyId: familyId)),
      child: const _FavorLedgerView(),
    );
  }
}

class _FavorLedgerView extends StatefulWidget {
  const _FavorLedgerView();

  @override
  State<_FavorLedgerView> createState() => _FavorLedgerViewState();
}

class _FavorLedgerViewState extends State<_FavorLedgerView>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _searchController.addListener(() {
      setState(() {
        _searchQuery = _searchController.text.toLowerCase();
      });
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.cardBackground,
        elevation: 0,
        title: Text(
          '人情账本',
          style: AppTextStyles.headline6.copyWith(color: AppColors.textPrimary),
        ),
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
        actions: [
          IconButton(
            onPressed: _showAddRecord,
            icon: const Icon(Icons.add),
            color: AppColors.primary,
          ),
        ],
      ),
      body: BlocBuilder<FavorLedgerBloc, FavorLedgerState>(
        builder: (context, state) {
          if (state is FavorLedgerLoading) {
            return const Center(
              child: CircularProgressIndicator(color: AppColors.primary),
            );
          }

          if (state is FavorLedgerError) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.error_outline, size: 48, color: AppColors.textTertiary),
                  const SizedBox(height: 16),
                  Text(
                    state.message,
                    style: AppTextStyles.subtitle1.copyWith(color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: () => context
                        .read<FavorLedgerBloc>()
                        .add(const FavorLedgerRefreshRequested()),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                    ),
                    child: const Text('重试'),
                  ),
                ],
              ),
            );
          }

          if (state is FavorLedgerLoaded) {
            return Column(
              children: [
                _buildSummaryCard(state.statistics),
                _buildTabBar(),
                Expanded(child: _buildTabContent(state)),
              ],
            );
          }

          return const SizedBox.shrink();
        },
      ),
    );
  }

  Widget _buildSummaryCard(FavorStatistics stats) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(20),
        boxShadow: AppColors.cardShadow,
      ),
      child: Column(
        children: [
          // Balance
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '净余额',
                style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
              ),
              const SizedBox(width: 8),
              if (stats.pendingCount > 0)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppColors.warning.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '${stats.pendingCount}待回',
                    style: AppTextStyles.overline.copyWith(
                      color: AppColors.warning,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                stats.netBalance >= 0 ? '+' : '',
                style: TextStyle(
                  color: stats.netBalance >= 0 ? AppColors.success : AppColors.error,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                '¥${stats.netBalance.abs().toStringAsFixed(0)}',
                style: TextStyle(
                  color: stats.netBalance >= 0 ? AppColors.success : AppColors.error,
                  fontSize: 36,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Icon(
                stats.netBalance >= 0 ? Icons.trending_up : Icons.trending_down,
                color: stats.netBalance >= 0 ? AppColors.success : AppColors.error,
                size: 28,
              ),
            ],
          ),

          const SizedBox(height: 20),
          Divider(color: AppColors.divider),
          const SizedBox(height: 16),

          // Received vs Given
          Row(
            children: [
              Expanded(
                child: _buildStatColumn(
                  label: '他人赠予',
                  amount: stats.totalReceived,
                  color: AppColors.success,
                  icon: Icons.arrow_downward,
                ),
              ),
              Container(
                width: 1,
                height: 40,
                color: AppColors.divider,
              ),
              Expanded(
                child: _buildStatColumn(
                  label: '我方赠出',
                  amount: stats.totalGiven,
                  color: AppColors.error,
                  icon: Icons.arrow_upward,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatColumn({
    required String label,
    required double amount,
    required Color color,
    required IconData icon,
  }) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
            Text(
              label,
              style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          '¥${amount.toStringAsFixed(0)}',
          style: AppTextStyles.headline6.copyWith(color: AppColors.textPrimary),
        ),
      ],
    );
  }

  Widget _buildTabBar() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: AppColors.chipBackground,
        borderRadius: BorderRadius.circular(12),
      ),
      child: TabBar(
        controller: _tabController,
        indicator: BoxDecoration(
          color: AppColors.primary,
          borderRadius: BorderRadius.circular(10),
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        dividerColor: Colors.transparent,
        labelColor: Colors.white,
        unselectedLabelColor: AppColors.textSecondary,
        labelStyle: AppTextStyles.button.copyWith(fontWeight: FontWeight.w600),
        unselectedLabelStyle: AppTextStyles.button,
        tabs: const [
          Tab(text: '全部记录'),
          Tab(text: '待回礼'),
          Tab(text: '联系人'),
        ],
      ),
    );
  }

  Widget _buildTabContent(FavorLedgerLoaded state) {
    return TabBarView(
      controller: _tabController,
      children: [
        _buildRecordsList(state.records),
        _buildRecordsList(state.pendingRecords),
        _buildContactsList(state.contacts),
      ],
    );
  }

  Widget _buildRecordsList(List<FavorRecord> records) {
    if (records.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.receipt_long, size: 48, color: AppColors.textTertiary),
            const SizedBox(height: 16),
            Text(
              '暂无记录',
              style: AppTextStyles.subtitle1.copyWith(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 8),
            Text(
              '点击右上角添加人情记录',
              style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: records.length,
      itemBuilder: (context, index) {
        final record = records[index];
        return _buildRecordCard(record);
      },
    );
  }

  Widget _buildRecordCard(FavorRecord record) {
    final isReceive = record.direction == 'receive';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppColors.cardShadow,
      ),
      child: Row(
        children: [
          // Direction indicator
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: (isReceive ? AppColors.success : AppColors.error)
                  .withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              isReceive ? Icons.arrow_downward : Icons.arrow_upward,
              color: isReceive ? AppColors.success : AppColors.error,
            ),
          ),
          const SizedBox(width: 12),

          // Details
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        record.contactName,
                        style: AppTextStyles.subtitle1.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 8),
                    _buildEventChip(record.eventType),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(
                      record.date,
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                    if (record.status == 'pending') ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.warning.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          '待回礼',
                          style: AppTextStyles.overline.copyWith(
                            color: AppColors.warning,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),

          // Amount
          Text(
            '${isReceive ? '+' : '-'}¥${record.amount.toStringAsFixed(0)}',
            style: AppTextStyles.subtitle1.copyWith(
              color: isReceive ? AppColors.success : AppColors.error,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEventChip(String eventType) {
    final Map<String, String> eventLabels = {
      'wedding': '婚礼',
      'funeral': '丧礼',
      'birthday': '生日',
      'baby': '满月',
      'housewarming': '乔迁',
      'other': '其他',
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.chipBackground,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        eventLabels[eventType] ?? '其他',
        style: AppTextStyles.overline.copyWith(color: AppColors.primary),
      ),
    );
  }

  Widget _buildContactsList(List<FavorContact> contacts) {
    // Filter contacts based on search query
    final filteredContacts = _searchQuery.isEmpty
        ? contacts
        : contacts.where((contact) {
            final name = contact.name.toLowerCase();
            final position = (contact.position ?? '').toLowerCase();
            final company = (contact.company ?? '').toLowerCase();
            return name.contains(_searchQuery) ||
                position.contains(_searchQuery) ||
                company.contains(_searchQuery);
          }).toList();

    return Column(
      children: [
        // Search field
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: TextField(
            controller: _searchController,
            decoration: InputDecoration(
              hintText: '搜索联系人、职位、公司...',
              hintStyle: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
              prefixIcon: const Icon(Icons.search, color: AppColors.textTertiary),
              suffixIcon: _searchQuery.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear, size: 18),
                      onPressed: () => _searchController.clear(),
                    )
                  : null,
              filled: true,
              fillColor: AppColors.chipBackground,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            ),
          ),
        ),

        // Contacts list
        Expanded(
          child: filteredContacts.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.people_outline, size: 48, color: AppColors.textTertiary),
                      const SizedBox(height: 16),
                      Text(
                        _searchQuery.isEmpty ? '暂无联系人' : '未找到匹配的联系人',
                        style: AppTextStyles.subtitle1.copyWith(color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: filteredContacts.length,
                  itemBuilder: (context, index) {
                    final contact = filteredContacts[index];
                    return _buildContactCard(contact);
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildContactCard(FavorContact contact) {
    final isPositive = contact.balance > 0;
    final hasWorkInfo = contact.position != null || contact.company != null;
    final workInfo = [
      if (contact.position != null) contact.position,
      if (contact.company != null) contact.company,
    ].join(' · ');

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppColors.cardShadow,
      ),
      child: Row(
        children: [
          // Avatar
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: Text(
                contact.name.isNotEmpty ? contact.name.substring(0, 1) : '?',
                style: AppTextStyles.subtitle1.copyWith(
                  color: AppColors.primary,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),

          // Name and stats
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  contact.name,
                  style: AppTextStyles.subtitle1.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (hasWorkInfo) ...[
                  const SizedBox(height: 2),
                  Text(
                    workInfo,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(
                      '收 ¥${contact.totalReceived.toStringAsFixed(0)}',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.success,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Text(
                      '出 ¥${contact.totalGiven.toStringAsFixed(0)}',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.error,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Balance
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${isPositive ? '+' : ''}¥${contact.balance.toStringAsFixed(0)}',
                style: AppTextStyles.subtitle1.copyWith(
                  color: isPositive ? AppColors.success : AppColors.error,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                isPositive ? '他欠我' : '我欠他',
                style: AppTextStyles.overline.copyWith(
                  color: AppColors.textTertiary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _showAddRecord() {
    if (!mounted) return;

    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.cardBackground,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '添加人情记录',
                style: AppTextStyles.headline6,
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: _buildAddOption(
                      icon: Icons.arrow_downward,
                      label: '收到礼金',
                      color: AppColors.success,
                      onTap: () {
                        Navigator.pop(sheetContext);
                        _showAddFavorForm(isReceive: true);
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildAddOption(
                      icon: Icons.arrow_upward,
                      label: '送出礼金',
                      color: AppColors.error,
                      onTap: () {
                        Navigator.pop(sheetContext);
                        _showAddFavorForm(isReceive: false);
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  void _showAddFavorForm({required bool isReceive}) {
    if (!mounted) return;

    final state = context.read<FavorLedgerBloc>().state;
    final members = state is FavorLedgerLoaded ? state.members : <Member>[];

    final contactNameController = TextEditingController();
    final amountController = TextEditingController();
    String selectedEventType = 'other';
    Member? selectedMember;
    bool useManualInput = members.isEmpty;

    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.cardBackground,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) => StatefulBuilder(
        builder: (builderContext, setSheetState) => SafeArea(
          child: Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 20,
              bottom: MediaQuery.of(builderContext).viewInsets.bottom + 20,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      isReceive ? '记录收礼' : '记录送礼',
                      style: AppTextStyles.headline6,
                    ),
                    IconButton(
                      onPressed: () => Navigator.pop(sheetContext),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Contact selection section
                if (members.isNotEmpty) ...[
                  // Toggle between member selection and manual input
                  Row(
                    children: [
                      Expanded(
                        child: GestureDetector(
                          onTap: () => setSheetState(() => useManualInput = false),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            decoration: BoxDecoration(
                              color: !useManualInput
                                  ? AppColors.primary
                                  : AppColors.chipBackground,
                              borderRadius: const BorderRadius.horizontal(
                                left: Radius.circular(8),
                              ),
                            ),
                            child: Text(
                              '选择成员',
                              textAlign: TextAlign.center,
                              style: AppTextStyles.button.copyWith(
                                color: !useManualInput
                                    ? Colors.white
                                    : AppColors.textSecondary,
                              ),
                            ),
                          ),
                        ),
                      ),
                      Expanded(
                        child: GestureDetector(
                          onTap: () => setSheetState(() {
                            useManualInput = true;
                            selectedMember = null;
                          }),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            decoration: BoxDecoration(
                              color: useManualInput
                                  ? AppColors.primary
                                  : AppColors.chipBackground,
                              borderRadius: const BorderRadius.horizontal(
                                right: Radius.circular(8),
                              ),
                            ),
                            child: Text(
                              '手动输入',
                              textAlign: TextAlign.center,
                              style: AppTextStyles.button.copyWith(
                                color: useManualInput
                                    ? Colors.white
                                    : AppColors.textSecondary,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                ],

                // Member dropdown or text input
                if (!useManualInput && members.isNotEmpty)
                  DropdownButtonFormField<Member>(
                    value: selectedMember,
                    isExpanded: true,
                    decoration: InputDecoration(
                      labelText: '选择联系人',
                      filled: true,
                      fillColor: AppColors.chipBackground,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                    ),
                    hint: const Text('请选择联系人'),
                    items: members.map((member) {
                      final relation = member.relationText.isNotEmpty
                          ? ' (${member.relationText})'
                          : '';
                      return DropdownMenuItem<Member>(
                        value: member,
                        child: Text(
                          '${member.displayName}$relation',
                          style: AppTextStyles.subtitle1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      );
                    }).toList(),
                    onChanged: (value) {
                      setSheetState(() {
                        selectedMember = value;
                        if (value != null) {
                          contactNameController.text = value.displayName;
                        }
                      });
                    },
                  )
                else
                  TextField(
                    controller: contactNameController,
                    decoration: InputDecoration(
                      labelText: '联系人姓名',
                      hintText: '请输入联系人姓名',
                      filled: true,
                      fillColor: AppColors.chipBackground,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                const SizedBox(height: 12),

                TextField(
                  controller: amountController,
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(
                    labelText: '金额',
                    hintText: '请输入金额',
                    prefixText: '¥ ',
                    filled: true,
                    fillColor: AppColors.chipBackground,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: selectedEventType,
                  decoration: InputDecoration(
                    labelText: '事件类型',
                    filled: true,
                    fillColor: AppColors.chipBackground,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'wedding', child: Text('婚礼')),
                    DropdownMenuItem(value: 'funeral', child: Text('丧礼')),
                    DropdownMenuItem(value: 'birthday', child: Text('生日')),
                    DropdownMenuItem(value: 'baby', child: Text('满月')),
                    DropdownMenuItem(value: 'housewarming', child: Text('乔迁')),
                    DropdownMenuItem(value: 'other', child: Text('其他')),
                  ],
                  onChanged: (value) {
                    if (value != null) {
                      setSheetState(() => selectedEventType = value);
                    }
                  },
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () {
                      // Get contact info
                      final name = selectedMember?.displayName ??
                          contactNameController.text.trim();
                      final contactId = selectedMember?.id;

                      final amountText = amountController.text.trim();
                      if (name.isEmpty || amountText.isEmpty) {
                        ScaffoldMessenger.of(builderContext).showSnackBar(
                          const SnackBar(content: Text('请填写完整信息')),
                        );
                        return;
                      }
                      final amount = double.tryParse(amountText);
                      if (amount == null || amount <= 0) {
                        ScaffoldMessenger.of(builderContext).showSnackBar(
                          const SnackBar(content: Text('请输入有效金额')),
                        );
                        return;
                      }
                      Navigator.pop(sheetContext);
                      context.read<FavorLedgerBloc>().add(
                        FavorCreateRequested(
                          contactName: name,
                          contactId: contactId,
                          amount: amount,
                          direction: isReceive ? 'receive' : 'give',
                          eventType: selectedEventType,
                        ),
                      );
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text('已记录: ${isReceive ? "收到" : "送出"} ¥$amount ${isReceive ? "来自" : "给"} $name'),
                          backgroundColor: isReceive ? AppColors.success : AppColors.error,
                        ),
                      );
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: isReceive ? AppColors.success : AppColors.error,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: Text(isReceive ? '确认收礼' : '确认送礼'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAddOption({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Material(
      color: color.withValues(alpha: 0.1),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              Icon(icon, color: color, size: 32),
              const SizedBox(height: 8),
              Text(
                label,
                style: AppTextStyles.button.copyWith(color: color),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
