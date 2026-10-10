import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/transaction.dart';
import '../bloc/finance_bloc.dart';

class FinancePage extends StatefulWidget {
  const FinancePage({super.key});

  @override
  State<FinancePage> createState() => _FinancePageState();
}

class _FinancePageState extends State<FinancePage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late int _selectedYear;
  late int _selectedMonth;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    final now = DateTime.now();
    _selectedYear = now.year;
    _selectedMonth = now.month;

    // Load data
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _loadData();
    });
  }

  void _loadData() {
    context.read<FinanceBloc>().add(
      FinanceLoadRequested(year: _selectedYear, month: _selectedMonth),
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: BlocConsumer<FinanceBloc, FinanceState>(
          listener: (context, state) {
            if (state is FinanceError) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text(state.message)),
              );
            } else if (state is FinanceOperationSuccess) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(state.message),
                  backgroundColor: AppColors.success,
                ),
              );
            }
          },
          builder: (context, state) {
            return Column(
              children: [
                _buildHeader(),
                _buildSummaryCard(state),
                _buildTabBar(),
                Expanded(child: _buildContent(state)),
              ],
            );
          },
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showAddTransactionDialog(context),
        backgroundColor: AppColors.primary,
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Text('财务管理', style: AppTextStyles.headline4),
          const Spacer(),
          _buildMonthSelector(),
        ],
      ),
    );
  }

  Widget _buildMonthSelector() {
    return InkWell(
      onTap: _selectMonth,
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: AppColors.primary.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          children: [
            Text(
              '$_selectedYear年$_selectedMonth月',
              style: AppTextStyles.bodyText2.copyWith(
                color: AppColors.primary,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(width: 4),
            const Icon(Icons.keyboard_arrow_down,
                color: AppColors.primary, size: 18),
          ],
        ),
      ),
    );
  }

  Widget _buildSummaryCard(FinanceState state) {
    double totalIncome = 0;
    double totalExpense = 0;

    if (state is FinanceLoaded) {
      totalIncome = state.totalIncome;
      totalExpense = state.totalExpense;
    }

    final balance = totalIncome - totalExpense;
    final savingRate = totalIncome > 0
        ? (balance / totalIncome * 100).toStringAsFixed(1)
        : '0';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildSummaryItem(
                  '收入',
                  totalIncome,
                  Icons.arrow_downward,
                  Colors.greenAccent,
                ),
              ),
              Container(
                width: 1,
                height: 40,
                color: Colors.white.withValues(alpha: 0.3),
              ),
              Expanded(
                child: _buildSummaryItem(
                  '支出',
                  totalExpense,
                  Icons.arrow_upward,
                  Colors.redAccent,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '本月结余',
                      style: AppTextStyles.caption.copyWith(
                        color: Colors.white.withValues(alpha: 0.8),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '¥${balance.toStringAsFixed(2)}',
                      style: AppTextStyles.headline5.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '储蓄率 $savingRate%',
                    style: AppTextStyles.caption.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryItem(
    String label,
    double amount,
    IconData icon,
    Color iconColor,
  ) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 20,
              height: 20,
              decoration: BoxDecoration(
                color: iconColor.withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: iconColor, size: 12),
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: AppTextStyles.caption.copyWith(
                color: Colors.white.withValues(alpha: 0.8),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          '¥${amount.toStringAsFixed(2)}',
          style: AppTextStyles.subtitle1.copyWith(
            color: Colors.white,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  Widget _buildTabBar() {
    return Container(
      margin: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
      ),
      child: TabBar(
        controller: _tabController,
        indicator: BoxDecoration(
          color: AppColors.primary,
          borderRadius: BorderRadius.circular(10),
        ),
        labelColor: Colors.white,
        unselectedLabelColor: AppColors.textSecondary,
        labelStyle: AppTextStyles.bodyText2.copyWith(fontWeight: FontWeight.w600),
        dividerColor: Colors.transparent,
        tabs: const [
          Tab(text: '明细'),
          Tab(text: '统计'),
          Tab(text: '预算'),
        ],
      ),
    );
  }

  Widget _buildContent(FinanceState state) {
    return TabBarView(
      controller: _tabController,
      physics: const NeverScrollableScrollPhysics(),
      children: [
        _buildTransactionList(state),
        _buildStatistics(state),
        _buildBudget(),
      ],
    );
  }

  Widget _buildTransactionList(FinanceState state) {
    if (state is FinanceLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state is! FinanceLoaded || state.transactions.isEmpty) {
      return _buildEmptyState('暂无交易记录', '点击右下角按钮记录收支');
    }

    return RefreshIndicator(
      onRefresh: () async => _loadData(),
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        itemCount: state.transactions.length,
        itemBuilder: (context, index) {
          final tx = state.transactions[index];
          return Dismissible(
            key: Key(tx.id),
            direction: DismissDirection.endToStart,
            background: Container(
              alignment: Alignment.centerRight,
              padding: const EdgeInsets.only(right: 20),
              color: AppColors.error,
              child: const Icon(Icons.delete, color: Colors.white),
            ),
            onDismissed: (_) {
              context.read<FinanceBloc>().add(TransactionDeleteRequested(tx.id));
            },
            child: GestureDetector(
              onTap: () => _showEditTransactionDialog(context, tx),
              child: _buildTransactionItem(tx),
            ),
          );
        },
      ),
    );
  }

  Widget _buildTransactionItem(Transaction tx) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: (tx.isIncome ? AppColors.success : AppColors.error)
                  .withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: Text(tx.categoryIcon, style: const TextStyle(fontSize: 20)),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(tx.categoryName, style: AppTextStyles.bodyText1),
                if (tx.description != null)
                  Text(
                    tx.description!,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${tx.isIncome ? '+' : '-'}¥${tx.amount.toStringAsFixed(2)}',
                style: AppTextStyles.subtitle2.copyWith(
                  color: tx.isIncome ? AppColors.success : AppColors.error,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                DateFormat('M/d').format(tx.date),
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.textTertiary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatistics(FinanceState state) {
    if (state is! FinanceLoaded) {
      return const Center(child: CircularProgressIndicator());
    }

    final breakdown = state.categoryBreakdown;
    final totalExpense = state.totalExpense;

    if (breakdown.isEmpty || totalExpense == 0) {
      return _buildEmptyState('暂无统计数据', '添加支出后查看分类统计');
    }

    final sortedCategories = breakdown.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('支出分布', style: AppTextStyles.subtitle1),
          const SizedBox(height: 16),
          AspectRatio(
            aspectRatio: 1.3,
            child: PieChart(
              PieChartData(
                sections: _getChartSections(sortedCategories, totalExpense),
                centerSpaceRadius: 60,
                sectionsSpace: 2,
              ),
            ),
          ),
          const SizedBox(height: 24),
          Text('分类明细', style: AppTextStyles.subtitle1),
          const SizedBox(height: 12),
          ...sortedCategories.map((entry) => _buildCategoryDetail(
            entry.key,
            entry.value,
            totalExpense,
            _getCategoryColor(entry.key),
          )),
        ],
      ),
    );
  }

  List<PieChartSectionData> _getChartSections(
    List<MapEntry<TransactionCategory, double>> categories,
    double total,
  ) {
    return categories.map((entry) {
      final percentage = (entry.value / total * 100);
      return PieChartSectionData(
        value: entry.value,
        color: _getCategoryColor(entry.key),
        title: '${percentage.toStringAsFixed(0)}%',
        radius: 40,
        titleStyle: const TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.bold,
          color: Colors.white,
        ),
      );
    }).toList();
  }

  Widget _buildCategoryDetail(
    TransactionCategory category,
    double amount,
    double total,
    Color color,
  ) {
    final percentage = (amount / total * 100);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(3),
            ),
          ),
          const SizedBox(width: 8),
          Text(_getCategoryDisplayName(category), style: AppTextStyles.bodyText2),
          const Spacer(),
          Text(
            '¥${amount.toStringAsFixed(0)}',
            style: AppTextStyles.bodyText2.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            '${percentage.toStringAsFixed(1)}%',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Color _getCategoryColor(TransactionCategory category) {
    switch (category) {
      case TransactionCategory.food:
        return const Color(0xFFFF6B6B);
      case TransactionCategory.transport:
        return const Color(0xFF4ECDC4);
      case TransactionCategory.shopping:
        return const Color(0xFFFFE66D);
      case TransactionCategory.entertainment:
        return const Color(0xFF95E1D3);
      case TransactionCategory.housing:
        return const Color(0xFF6C5CE7);
      case TransactionCategory.utilities:
        return const Color(0xFF74B9FF);
      case TransactionCategory.medical:
        return const Color(0xFFE17055);
      case TransactionCategory.education:
        return const Color(0xFF00B894);
      case TransactionCategory.travel:
        return const Color(0xFF0984E3);
      case TransactionCategory.childcare:
        return const Color(0xFFFDAC53);
      case TransactionCategory.gift:
        return const Color(0xFFE84393);
      default:
        return const Color(0xFFA8A8A8);
    }
  }

  String _getCategoryDisplayName(TransactionCategory category) {
    switch (category) {
      case TransactionCategory.food:
        return '餐饮';
      case TransactionCategory.transport:
        return '交通';
      case TransactionCategory.shopping:
        return '购物';
      case TransactionCategory.entertainment:
        return '娱乐';
      case TransactionCategory.housing:
        return '住房';
      case TransactionCategory.utilities:
        return '水电燃气';
      case TransactionCategory.medical:
        return '医疗';
      case TransactionCategory.education:
        return '教育';
      case TransactionCategory.travel:
        return '旅行';
      case TransactionCategory.childcare:
        return '育儿';
      case TransactionCategory.gift:
        return '礼物';
      default:
        return '其他';
    }
  }

  Widget _buildBudget() {
    return BlocBuilder<FinanceBloc, FinanceState>(
      builder: (context, state) {
        if (state is! FinanceLoaded) {
          return const Center(child: CircularProgressIndicator());
        }

        final categoryBreakdown = state.categoryBreakdown;
        if (categoryBreakdown.isEmpty) {
          return _buildEmptyState('暂无支出数据', '添加支出后可设置预算');
        }

        // Sort by amount descending
        final sortedCategories = categoryBreakdown.entries.toList()
          ..sort((a, b) => b.value.compareTo(a.value));

        return ListView(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          children: [
            // Info card about budget feature
            Container(
              padding: const EdgeInsets.all(16),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, color: AppColors.primary, size: 20),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      '预算设置功能即将上线，以下为本月各分类支出情况',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.primary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            // Spending by category
            Container(
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
                      Text('本月支出分布', style: AppTextStyles.subtitle1),
                      const Spacer(),
                      Text(
                        '¥${state.totalExpense.toStringAsFixed(0)}',
                        style: AppTextStyles.subtitle2.copyWith(
                          color: AppColors.error,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  ...sortedCategories.take(8).map((entry) {
                    final percentage = state.totalExpense > 0
                        ? (entry.value / state.totalExpense * 100)
                        : 0.0;
                    return _buildSpendingItem(
                      _getCategoryDisplayName(entry.key),
                      entry.value,
                      percentage,
                      _getCategoryColor(entry.key),
                    );
                  }),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildSpendingItem(
    String name,
    double amount,
    double percentage,
    Color color,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
              const SizedBox(width: 8),
              Text(name, style: AppTextStyles.bodyText2),
              const Spacer(),
              Text(
                '¥${amount.toStringAsFixed(0)}',
                style: AppTextStyles.bodyText2.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '${percentage.toStringAsFixed(1)}%',
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (percentage / 100).clamp(0, 1).toDouble(),
              backgroundColor: AppColors.background,
              valueColor: AlwaysStoppedAnimation(color),
              minHeight: 6,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(String title, String subtitle) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.account_balance_wallet_outlined,
              size: 64, color: AppColors.textTertiary),
          const SizedBox(height: 16),
          Text(title, style: AppTextStyles.subtitle1),
          const SizedBox(height: 8),
          Text(
            subtitle,
            style: AppTextStyles.bodyText2.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _selectMonth() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime(_selectedYear, _selectedMonth),
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
      initialDatePickerMode: DatePickerMode.year,
    );

    if (picked != null) {
      setState(() {
        _selectedYear = picked.year;
        _selectedMonth = picked.month;
      });
      context.read<FinanceBloc>().add(
        MonthChanged(year: _selectedYear, month: _selectedMonth),
      );
    }
  }

  void _showAddTransactionDialog(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      isDismissible: true,
      enableDrag: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => _AddTransactionSheet(
        onSave: (transaction) {
          Navigator.pop(sheetContext);
          context.read<FinanceBloc>().add(TransactionCreateRequested(transaction));
        },
      ),
    );
  }

  void _showEditTransactionDialog(BuildContext context, Transaction existingTransaction) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      isDismissible: true,
      enableDrag: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => _AddTransactionSheet(
        existingTransaction: existingTransaction,
        onSave: (transaction) {
          Navigator.pop(sheetContext);
          context.read<FinanceBloc>().add(
            TransactionUpdateRequested(existingTransaction.id, transaction),
          );
        },
      ),
    );
  }
}

class _AddTransactionSheet extends StatefulWidget {
  final Function(Transaction) onSave;
  final Transaction? existingTransaction;

  const _AddTransactionSheet({
    required this.onSave,
    this.existingTransaction,
  });

  bool get isEditing => existingTransaction != null;

  @override
  State<_AddTransactionSheet> createState() => _AddTransactionSheetState();
}

class _AddTransactionSheetState extends State<_AddTransactionSheet> {
  late bool _isExpense;
  late TransactionCategory _selectedCategory;
  PaymentMethod? _selectedPaymentMethod;
  late TextEditingController _amountController;
  late TextEditingController _descriptionController;
  late TextEditingController _merchantController;
  late DateTime _selectedDate;

  @override
  void initState() {
    super.initState();
    final tx = widget.existingTransaction;
    _isExpense = tx?.isExpense ?? true;
    _selectedCategory = tx?.category ?? TransactionCategory.food;
    _selectedPaymentMethod = tx?.paymentMethod;
    _selectedDate = tx?.date ?? DateTime.now();
    _amountController = TextEditingController(
      text: tx != null ? tx.amount.toString() : '',
    );
    _descriptionController = TextEditingController(
      text: tx?.description ?? '',
    );
    _merchantController = TextEditingController(
      text: tx?.merchant ?? '',
    );
  }

  final List<(PaymentMethod, String, String)> _paymentMethods = [
    (PaymentMethod.cash, '现金', '💵'),
    (PaymentMethod.card, '银行卡', '💳'),
    (PaymentMethod.wechat, '微信', '📱'),
    (PaymentMethod.alipay, '支付宝', '📲'),
    (PaymentMethod.transfer, '转账', '🏦'),
    (PaymentMethod.other, '其他', '💰'),
  ];

  final List<(TransactionCategory, String, String)> _expenseCategories = [
    (TransactionCategory.food, '餐饮', '🍔'),
    (TransactionCategory.transport, '交通', '🚗'),
    (TransactionCategory.shopping, '购物', '🛒'),
    (TransactionCategory.entertainment, '娱乐', '🎬'),
    (TransactionCategory.housing, '住房', '🏠'),
    (TransactionCategory.utilities, '水电燃气', '💡'),
    (TransactionCategory.medical, '医疗', '🏥'),
    (TransactionCategory.education, '教育', '📚'),
    (TransactionCategory.travel, '旅行', '✈️'),
    (TransactionCategory.childcare, '育儿', '👶'),
    (TransactionCategory.gift, '礼物', '🎀'),
    (TransactionCategory.other_expense, '其他', '📝'),
  ];

  final List<(TransactionCategory, String, String)> _incomeCategories = [
    (TransactionCategory.salary, '工资', '💰'),
    (TransactionCategory.bonus, '奖金', '🎁'),
    (TransactionCategory.investment, '投资', '📈'),
    (TransactionCategory.other_income, '其他', '💵'),
  ];

  @override
  void dispose() {
    _amountController.dispose();
    _descriptionController.dispose();
    _merchantController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.85,
      ),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildHandle(),
          _buildHeader(),
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildTypeSelector(),
                  const SizedBox(height: 20),
                  _buildAmountField(),
                  const SizedBox(height: 20),
                  _buildCategorySelector(),
                  const SizedBox(height: 20),
                  _buildPaymentMethodSelector(),
                  const SizedBox(height: 20),
                  _buildMerchantField(),
                  const SizedBox(height: 20),
                  _buildDescriptionField(),
                  const SizedBox(height: 24),
                  _buildSaveButton(),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHandle() {
    return GestureDetector(
      onTap: () => Navigator.pop(context),
      child: Container(
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
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: (_isExpense ? AppColors.error : AppColors.success).withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(
              _isExpense ? Icons.remove_circle_outline : Icons.add_circle_outline,
              color: _isExpense ? AppColors.error : AppColors.success,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.isEditing ? '编辑交易' : '记一笔',
                  style: AppTextStyles.headline5,
                ),
                const SizedBox(height: 2),
                Text(
                  widget.isEditing
                      ? '修改交易信息'
                      : (_isExpense ? '记录支出' : '记录收入'),
                  style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
                ),
              ],
            ),
          ),
          GestureDetector(
            onTap: () => Navigator.pop(context),
            child: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.close,
                color: AppColors.textSecondary,
                size: 20,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTypeSelector() {
    return Row(
      children: [
        Expanded(
          child: GestureDetector(
            onTap: () => setState(() {
              _isExpense = true;
              _selectedCategory = TransactionCategory.food;
            }),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: _isExpense ? AppColors.error : Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: _isExpense ? AppColors.error : AppColors.divider,
                ),
              ),
              child: Center(
                child: Text(
                  '支出',
                  style: AppTextStyles.subtitle2.copyWith(
                    color: _isExpense ? Colors.white : AppColors.textPrimary,
                    fontWeight: _isExpense ? FontWeight.bold : FontWeight.normal,
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: GestureDetector(
            onTap: () => setState(() {
              _isExpense = false;
              _selectedCategory = TransactionCategory.salary;
            }),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: !_isExpense ? AppColors.success : Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: !_isExpense ? AppColors.success : AppColors.divider,
                ),
              ),
              child: Center(
                child: Text(
                  '收入',
                  style: AppTextStyles.subtitle2.copyWith(
                    color: !_isExpense ? Colors.white : AppColors.textPrimary,
                    fontWeight: !_isExpense ? FontWeight.bold : FontWeight.normal,
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildAmountField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('金额', style: AppTextStyles.subtitle1),
        const SizedBox(height: 8),
        TextField(
          controller: _amountController,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          style: AppTextStyles.headline4.copyWith(
            color: _isExpense ? AppColors.error : AppColors.success,
          ),
          decoration: InputDecoration(
            prefixText: '¥ ',
            prefixStyle: AppTextStyles.headline4.copyWith(
              color: _isExpense ? AppColors.error : AppColors.success,
            ),
            hintText: '0.00',
            filled: true,
            fillColor: AppColors.background,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildCategorySelector() {
    final categories = _isExpense ? _expenseCategories : _incomeCategories;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('分类', style: AppTextStyles.subtitle1),
        const SizedBox(height: 12),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: categories.map((cat) {
            final isSelected = _selectedCategory == cat.$1;
            return GestureDetector(
              onTap: () => setState(() => _selectedCategory = cat.$1),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  color: isSelected
                      ? (_isExpense ? AppColors.error : AppColors.success)
                      : Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected
                        ? (_isExpense ? AppColors.error : AppColors.success)
                        : AppColors.divider,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(cat.$3, style: const TextStyle(fontSize: 16)),
                    const SizedBox(width: 6),
                    Text(
                      cat.$2,
                      style: AppTextStyles.bodyText2.copyWith(
                        color: isSelected ? Colors.white : AppColors.textPrimary,
                        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildPaymentMethodSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('支付方式（可选）', style: AppTextStyles.subtitle1),
        const SizedBox(height: 12),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: _paymentMethods.map((method) {
            final isSelected = _selectedPaymentMethod == method.$1;
            return GestureDetector(
              onTap: () => setState(() {
                _selectedPaymentMethod = isSelected ? null : method.$1;
              }),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  color: isSelected ? AppColors.primary : Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected ? AppColors.primary : AppColors.divider,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(method.$3, style: const TextStyle(fontSize: 14)),
                    const SizedBox(width: 4),
                    Text(
                      method.$2,
                      style: AppTextStyles.caption.copyWith(
                        color: isSelected ? Colors.white : AppColors.textPrimary,
                        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildMerchantField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('商家（可选）', style: AppTextStyles.subtitle1),
        const SizedBox(height: 8),
        TextField(
          controller: _merchantController,
          decoration: InputDecoration(
            hintText: '输入商家名称...',
            filled: true,
            fillColor: AppColors.background,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDescriptionField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('备注', style: AppTextStyles.subtitle1),
        const SizedBox(height: 8),
        TextField(
          controller: _descriptionController,
          decoration: InputDecoration(
            hintText: '添加备注...',
            filled: true,
            fillColor: AppColors.background,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSaveButton() {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton(
        onPressed: _saveTransaction,
        style: ElevatedButton.styleFrom(
          backgroundColor: _isExpense ? AppColors.error : AppColors.success,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
        child: Text(
          widget.isEditing ? '更新' : '保存',
          style: AppTextStyles.subtitle1.copyWith(
            color: Colors.white,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  void _saveTransaction() {
    final amountText = _amountController.text.trim();
    if (amountText.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('请输入金额'),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          backgroundColor: AppColors.error,
        ),
      );
      return;
    }

    final amount = double.tryParse(amountText);
    if (amount == null || amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('请输入有效金额'),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          backgroundColor: AppColors.error,
        ),
      );
      return;
    }

    final existingTx = widget.existingTransaction;
    final transaction = Transaction(
      id: existingTx?.id ?? DateTime.now().millisecondsSinceEpoch.toString(),
      type: _isExpense ? TransactionType.expense : TransactionType.income,
      category: _selectedCategory,
      amount: amount,
      description: _descriptionController.text.trim().isNotEmpty
          ? _descriptionController.text.trim()
          : null,
      paymentMethod: _selectedPaymentMethod,
      merchant: _merchantController.text.trim().isNotEmpty
          ? _merchantController.text.trim()
          : null,
      date: _selectedDate,
      createdAt: existingTx?.createdAt ?? DateTime.now(),
    );

    widget.onSave(transaction);
  }
}
