import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import 'conversation_page.dart';
import '../../../kanban/presentation/pages/curated_timeline_page.dart';
import '../../../profile/presentation/pages/profile_page.dart';

/// Main shell with 3-tab navigation following the redesigned layout.
///
/// Tabs:
/// 1. 对话 (Chat) - AI chat with morning briefing
/// 2. 时光轴 (Timeline) - Curated timeline and memory lane
/// 3. 我的 (Profile) - Members, settings, gifts, travel lists
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
  int _currentIndex = 0;
  bool _isAnimating = false;

  // 3-tab navigation
  final _tabs = [
    (
      icon: Icons.chat_bubble_outline,
      activeIcon: Icons.chat_bubble,
      label: '对话',
      route: Routes.conversation,
    ),
    (
      icon: Icons.timeline_outlined,
      activeIcon: Icons.timeline,
      label: '时光轴',
      route: Routes.kanban,
    ),
    (
      icon: Icons.person_outline,
      activeIcon: Icons.person,
      label: '我的',
      route: Routes.profile,
    ),
  ];

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialIndex.clamp(0, _tabs.length - 1);
    _pageController = PageController(initialPage: _currentIndex);

    // Initialize pages with their required BLoC providers
    _pages = [
      // Chat page uses the app-level AssistantBloc from root MultiBlocProvider.
      const ConversationPage(),
      // Kanban page (kanban board + memory lane)
      const CuratedTimelinePage(),
      // Profile page (members, settings, gifts, travel)
      const ProfilePage(),
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
          location.startsWith(Routes.insightGraph)) {
        newIndex = 0; // Chat (graph is accessible from chat)
      } else if (location.startsWith(Routes.schedule) ||
          location.startsWith(Routes.timeline)) {
        newIndex = 1; // Kanban
      } else if (location.startsWith(Routes.settings) ||
          location.startsWith(Routes.family) ||
          location.startsWith(Routes.members) ||
          location.startsWith(Routes.relationships) ||
          location.startsWith(Routes.trips) ||
          location.startsWith(Routes.gifts) ||
          location.startsWith(Routes.dates)) {
        newIndex = 2; // Profile
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
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                decoration: BoxDecoration(
                  color: isSelected
                      ? AppColors.primary.withValues(alpha: 0.1)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(
                  isSelected ? tab.activeIcon : tab.icon,
                  color:
                      isSelected ? AppColors.primary : AppColors.textTertiary,
                  size: 22,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                tab.label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  color:
                      isSelected ? AppColors.primary : AppColors.textTertiary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
