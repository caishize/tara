import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../domain/entities/trip.dart';
import '../bloc/trip_bloc.dart';
import '../widgets/trip_card.dart';

class TripPage extends StatefulWidget {
  const TripPage({super.key});

  @override
  State<TripPage> createState() => _TripPageState();
}

class _TripPageState extends State<TripPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  TripCategory? _selectedCategory;

  final List<_TabItem> _tabs = [
    _TabItem('全部', null),
    _TabItem('规划中', TripStatus.planning),
    _TabItem('已确认', TripStatus.confirmed),
    _TabItem('进行中', TripStatus.inProgress),
    _TabItem('已完成', TripStatus.completed),
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
    _tabController.addListener(_onTabChanged);
    // Delay load to ensure context is available
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _loadPlans();
    });
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  void _loadPlans() {
    context.read<TripBloc>().add(
      TripsLoadRequested(
        status: _tabs[_tabController.index].status,
        category: _selectedCategory,
      ),
    );
  }

  void _onTabChanged() {
    if (_tabController.indexIsChanging) return;
    _loadPlans();
  }

  void _onCategoryChanged(TripCategory? category) {
    setState(() {
      _selectedCategory = category;
    });
    _loadPlans();
  }

  void _navigateToDetail(String planId) {
    context.push('/trips/$planId').then((_) {
      // Reload plans when returning from detail page
      _loadPlans();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/dashboard');
            }
          },
        ),
        title: const Text('行程管理'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {
              // TODO: Implement search
            },
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(96),
          child: Column(
            children: [
              // Category filter
              _buildCategoryFilter(),
              // Status tabs
              TabBar(
                controller: _tabController,
                isScrollable: true,
                tabAlignment: TabAlignment.start,
                tabs: _tabs.map((t) => Tab(text: t.label)).toList(),
              ),
            ],
          ),
        ),
      ),
      body: BlocConsumer<TripBloc, TripState>(
        // Only listen to states relevant to the list page
        listenWhen: (previous, current) {
          return current is TripOperationSuccess ||
                 (current is TripsLoaded);
        },
        listener: (context, state) {
          if (state is TripOperationSuccess) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.message)),
            );
            _loadPlans();
          }
        },
        // Only rebuild for TripsLoaded - ignore loading/errors from detail page
        buildWhen: (previous, current) {
          // Only rebuild when we get a new list of plans
          return current is TripsLoaded;
        },
        builder: (context, state) {
          if (state is TripsLoaded) {
            return _buildPlansList(state.plans);
          }

          // Show loading for initial load or empty state
          return const Center(child: CircularProgressIndicator());
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          context.push('/trips/create');
        },
        icon: const Icon(Icons.add),
        label: const Text('新建行程'),
      ),
    );
  }

  Widget _buildCategoryFilter() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          _buildCategoryChip(null, '全部', Icons.list),
          const SizedBox(width: 8),
          _buildCategoryChip(TripCategory.personal, '个人出行', Icons.person),
          const SizedBox(width: 8),
          _buildCategoryChip(TripCategory.business, '公务差旅', Icons.business_center),
        ],
      ),
    );
  }

  Widget _buildCategoryChip(TripCategory? category, String label, IconData icon) {
    final isSelected = _selectedCategory == category;
    final theme = Theme.of(context);

    return FilterChip(
      label: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 16,
            color: isSelected
                ? theme.colorScheme.onPrimary
                : theme.colorScheme.onSurface,
          ),
          const SizedBox(width: 4),
          Text(label),
        ],
      ),
      selected: isSelected,
      onSelected: (_) => _onCategoryChanged(category),
      selectedColor: theme.colorScheme.primary,
      labelStyle: TextStyle(
        color: isSelected
            ? theme.colorScheme.onPrimary
            : theme.colorScheme.onSurface,
      ),
      checkmarkColor: theme.colorScheme.onPrimary,
      showCheckmark: false,
    );
  }

  Widget _buildPlansList(List<Trip> plans) {
    // Filter by category if selected
    final filteredPlans = _selectedCategory != null
        ? plans.where((p) => p.category == _selectedCategory).toList()
        : plans;

    if (filteredPlans.isEmpty) {
      return _buildEmptyState();
    }

    // Group plans by status for better display
    final upcomingPlans = filteredPlans.where((p) =>
      p.status == TripStatus.planning ||
      p.status == TripStatus.confirmed
    ).toList();

    final activePlans = filteredPlans.where((p) =>
      p.status == TripStatus.inProgress
    ).toList();

    final pastPlans = filteredPlans.where((p) =>
      p.status == TripStatus.completed ||
      p.status == TripStatus.cancelled
    ).toList();

    return RefreshIndicator(
      onRefresh: () async => _loadPlans(),
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (activePlans.isNotEmpty) ...[
            _buildSectionHeader('正在进行', Icons.flight_takeoff),
            ...activePlans.map((plan) => TripCard(
              plan: plan,
              onTap: () => _navigateToDetail(plan.id),
            )),
            const SizedBox(height: 16),
          ],
          if (upcomingPlans.isNotEmpty) ...[
            _buildSectionHeader('即将出发', Icons.event),
            ...upcomingPlans.map((plan) => TripCard(
              plan: plan,
              onTap: () => _navigateToDetail(plan.id),
            )),
            const SizedBox(height: 16),
          ],
          if (pastPlans.isNotEmpty) ...[
            _buildSectionHeader('历史行程', Icons.history),
            ...pastPlans.map((plan) => TripCard(
              plan: plan,
              onTap: () => _navigateToDetail(plan.id),
            )),
          ],
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Icon(icon, size: 20, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 8),
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    final categoryText = _selectedCategory == TripCategory.personal
        ? '个人出行'
        : _selectedCategory == TripCategory.business
            ? '公务差旅'
            : '';
    final emptyText = categoryText.isEmpty
        ? '还没有行程计划'
        : '还没有$categoryText计划';

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.luggage_outlined,
            size: 80,
            color: Colors.grey[400],
          ),
          const SizedBox(height: 16),
          Text(
            emptyText,
            style: TextStyle(
              fontSize: 18,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '点击下方按钮开始规划您的行程',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[500],
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () => context.push('/trips/create'),
            icon: const Icon(Icons.add),
            label: const Text('创建行程计划'),
          ),
        ],
      ),
    );
  }
}

class _TabItem {
  final String label;
  final TripStatus? status;

  _TabItem(this.label, this.status);
}
