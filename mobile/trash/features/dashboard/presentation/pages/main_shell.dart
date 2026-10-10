import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/di/injection.dart';
import '../../../assistant/presentation/bloc/assistant_bloc.dart';
import '../../../conversation/presentation/pages/conversation_page.dart';
import '../../../insight_graph/presentation/bloc/insight_graph_bloc.dart';
import '../../../insight_graph/presentation/bloc/insight_graph_event.dart';
import '../../../insight_graph/presentation/pages/insight_graph_page.dart';
import '../../../timeline/presentation/pages/curated_timeline_page.dart';
import '../../../family/presentation/pages/family_page.dart';
import '../../../settings/presentation/pages/settings_page.dart';

/// Main shell with 5-tab navigation following the new design.
///
/// Tabs:
/// 1. 对话 (Conversation) - AI chat with morning briefing
/// 2. 人情 (Social Ledger) - Contact and relationship management
/// 3. 时光轴 (Timeline) - Calendar and event timeline
/// 4. 家庭 (Family) - Family dashboard and household management
/// 5. 设置 (Settings) - Profile and app settings
class MainShell extends StatefulWidget {
  final Widget child;
  final int initialIndex;

  const MainShell({
    super.key,
    required this.child,
    this.initialIndex = 0,
  });

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  late PageController _pageController;
  late List<Widget> _pages;
  late InsightGraphBloc _insightGraphBloc;
  int _currentIndex = 0;
  bool _isAnimating = false;

  // New 5-tab navigation
  final _tabs = [
    (
      icon: Icons.chat_bubble_outline,
      activeIcon: Icons.chat_bubble,
      label: '对话',
      route: Routes.conversation,
    ),
    (
      icon: Icons.hub_outlined,
      activeIcon: Icons.hub,
      label: '图谱',
      route: Routes.insightGraph,
    ),
    (
      icon: Icons.access_time,
      activeIcon: Icons.access_time_filled,
      label: '时光轴',
      route: Routes.timeline,
    ),
    (
      icon: Icons.home_outlined,
      activeIcon: Icons.home,
      label: '家庭',
      route: Routes.family,
    ),
    (
      icon: Icons.settings_outlined,
      activeIcon: Icons.settings,
      label: '设置',
      route: Routes.settings,
    ),
  ];

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialIndex.clamp(0, _tabs.length - 1);
    _pageController = PageController(initialPage: _currentIndex);
    _insightGraphBloc = getIt<InsightGraphBloc>()
      ..add(const LoadInsightGraph())
      ..add(const LoadUpcomingTrips());

    // Initialize pages with their required BLoC providers
    _pages = [
      // Conversation page with AssistantBloc
      BlocProvider.value(
        value: getIt<AssistantBloc>(),
        child: const ConversationPage(),
      ),
      // Insight Graph page — BLoC managed here for tab-switch refresh
      BlocProvider<InsightGraphBloc>.value(
        value: _insightGraphBloc,
        child: const InsightGraphView(),
      ),
      // Timeline page (kanban + memory lane)
      const CuratedTimelinePage(),
      // Family page
      const FamilyPage(),
      // Settings page
      const SettingsPage(),
    ];
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncIndexFromRoute();
  }

  @override
  void didUpdateWidget(MainShell oldWidget) {
    super.didUpdateWidget(oldWidget);
    _syncIndexFromRoute();
  }

  void _syncIndexFromRoute() {
    final location = GoRouterState.of(context).matchedLocation;

    int? newIndex;

    for (int i = 0; i < _tabs.length; i++) {
      if (location == _tabs[i].route ||
          location.startsWith('${_tabs[i].route}/')) {
        newIndex = i;
        break;
      }
    }

    // Handle legacy routes
    if (newIndex == null) {
      if (location.startsWith(Routes.dashboard) ||
          location.startsWith(Routes.assistant) ||
          location.startsWith(Routes.dailyBriefing)) {
        newIndex = 0; // Conversation
      } else if (location.startsWith(Routes.socialLedger) ||
          location.startsWith(Routes.members) ||
          location.startsWith(Routes.relationships) ||
          location.startsWith(Routes.favorLedger)) {
        newIndex = 1; // Insight Graph (legacy social ledger routes)
      } else if (location.startsWith(Routes.schedule) ||
          location.startsWith(Routes.travel)) {
        newIndex = 2; // Timeline
      } else if (location.startsWith(Routes.shopping) ||
          location.startsWith(Routes.inventory)) {
        newIndex = 3; // Family
      } else if (location.startsWith(Routes.profile)) {
        newIndex = 4; // Settings
      }
    }

    if (newIndex != null && _currentIndex != newIndex) {
      setState(() => _currentIndex = newIndex!);
      if (_pageController.hasClients) {
        _isAnimating = true;
        _pageController
            .animateToPage(
              newIndex,
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeInOut,
            )
            .then((_) => _isAnimating = false);
      }
    }
  }

  void _onPageChanged(int index) {
    if (_currentIndex != index) {
      setState(() => _currentIndex = index);
      if (!_isAnimating) {
        context.go(_tabs[index].route);
      }
      // Refresh insight graph when switching back to the tab,
      // so deleted trips and stale associations are updated.
      if (index == 1) {
        _insightGraphBloc.add(const LoadUpcomingTrips());
      }
    }
  }

  void _onTabTapped(int index) {
    if (_currentIndex != index) {
      _isAnimating = true;
      _pageController
          .animateToPage(
            index,
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeInOut,
          )
          .then((_) {
        _isAnimating = false;
        context.go(_tabs[index].route);
      });
    }
  }

  @override
  void dispose() {
    _insightGraphBloc.close();
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: PageView(
        controller: _pageController,
        onPageChanged: _onPageChanged,
        physics: const ClampingScrollPhysics(),
        children: _pages,
      ),
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  Widget _buildBottomNav() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: AppColors.bottomNavShadow,
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: List.generate(
              _tabs.length,
              (index) => _buildTabItem(index),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTabItem(int index) {
    final tab = _tabs[index];
    final isSelected = _currentIndex == index;

    return Expanded(
      child: InkWell(
        onTap: () => _onTabTapped(index),
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                decoration: BoxDecoration(
                  color: isSelected
                      ? AppColors.primary.withValues(alpha: 0.1)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(
                  isSelected ? tab.activeIcon : tab.icon,
                  color: isSelected ? AppColors.primary : AppColors.textTertiary,
                  size: 22,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                tab.label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  color: isSelected ? AppColors.primary : AppColors.textTertiary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
