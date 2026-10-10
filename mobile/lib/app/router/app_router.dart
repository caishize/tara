import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/storage/auth_storage.dart';
import '../../features/auth/presentation/pages/login_page.dart';
import '../../features/auth/presentation/pages/splash_page.dart';
import '../../features/auth/presentation/pages/edit_profile_page.dart';
import '../../features/auth/presentation/pages/change_password_page.dart';
import '../../features/auth/presentation/pages/delete_account_page.dart';
import '../../features/chat/presentation/pages/main_shell.dart';
import '../../features/chat/presentation/pages/conversation_page.dart';
import '../../features/kanban/presentation/pages/event_detail_page.dart';
import '../../features/kanban/presentation/pages/insight_graph_page.dart';
import '../../features/kanban/data/models/kanban_models.dart';
import '../../features/kanban/presentation/pages/curated_timeline_page.dart';
import '../../features/kanban/presentation/pages/trip_memory_page.dart';
import '../../features/kanban/domain/entities/memory_lane.dart';
import '../../features/members/presentation/pages/members_page.dart';
import '../../features/members/presentation/pages/member_detail_page.dart';
import '../../features/members/presentation/pages/member_form_page.dart';
import '../../features/members/presentation/pages/work_history_form_page.dart';
import '../../features/members/presentation/pages/professional_relation_form_page.dart';
import '../../features/dates/presentation/pages/dates_page.dart';
import '../../features/dates/presentation/pages/date_detail_page.dart';
import '../../features/gifts/presentation/pages/gifts_page.dart';
import '../../features/gifts/presentation/pages/gift_entry_page.dart';
import '../../features/gifts/presentation/pages/gift_recommendation_page.dart';
import '../../features/gifts/presentation/bloc/gifts_bloc.dart';
import '../../features/profile/presentation/pages/profile_page.dart';
import '../../features/profile/presentation/pages/smart_services_page.dart';
import '../../features/profile/presentation/pages/app_settings_page.dart';
import '../../features/profile/presentation/pages/privacy_security_page.dart';
import '../../features/profile/presentation/pages/data_backup_page.dart';
import '../../features/profile/presentation/pages/help_feedback_page.dart';
import '../../features/profile/presentation/pages/about_page.dart';
import '../../features/profile/presentation/pages/activity_timeline_page.dart';
import '../../features/profile/presentation/pages/work_report_page.dart';
import '../../features/profile/presentation/pages/curation_detail_page.dart';
import '../../features/profile/presentation/pages/insight_settings_page.dart';
import '../../features/profile/presentation/pages/connections_page.dart';
import '../../features/profile/presentation/pages/connection_detail_page.dart';
import '../../features/profile/presentation/pages/memory_browser_page.dart';
import '../../features/profile/presentation/pages/memory_detail_page.dart';
import '../../features/profile/presentation/pages/insight_history_page.dart';
import '../../features/profile/presentation/pages/service_detail_page.dart';
import '../../features/profile/data/models/connection_model.dart';
import '../../features/profile/data/models/memory_item_model.dart';
import '../../features/profile/domain/entities/smart_service.dart';
import '../../features/trip/presentation/pages/trip_page.dart';
import '../../features/trip/presentation/pages/trip_detail_page.dart';
import '../../features/trip/presentation/pages/create_trip_page.dart';
import '../../features/trip/presentation/pages/add_expense_page.dart';
import '../../features/trip/presentation/pages/destination_recommendation_page.dart';
import '../../features/trip/presentation/pages/memory_gallery_page.dart';
import '../../features/trip/presentation/pages/trip_feedback_page.dart';
import '../../features/relationships/presentation/pages/relationships_page.dart';
import '../../features/relationships/presentation/pages/relationship_graph_page.dart';
import '../../features/relationships/presentation/pages/favor_ledger_page.dart';
import '../../features/relationships/presentation/pages/smart_groups_page.dart';
import '../../features/relationships/presentation/bloc/relationships_bloc.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../di/injection.dart';

import 'routes.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();

// Routes that don't require authentication
const _publicRoutes = [Routes.splash, Routes.login];

GoRouter createAppRouter(AuthStorage authStorage) => GoRouter(
  navigatorKey: _rootNavigatorKey,
  initialLocation: Routes.splash,
  debugLogDiagnostics: true,
  redirect: (context, state) {
    final isAuthenticated = authStorage.isAuthenticated;
    final isPublicRoute = _publicRoutes.contains(state.matchedLocation);

    if (state.matchedLocation == Routes.splash) {
      return null;
    }

    if (!isAuthenticated && !isPublicRoute) {
      return Routes.login;
    }

    if (isAuthenticated && state.matchedLocation == Routes.login) {
      return Routes.conversation;
    }

    // Legacy route redirects
    if (state.matchedLocation == Routes.dashboard) {
      return Routes.conversation;
    }
    if (state.matchedLocation == Routes.schedule ||
        state.matchedLocation == Routes.timeline) {
      return Routes.kanban;
    }
    if (state.matchedLocation == Routes.family ||
        state.matchedLocation == Routes.settings) {
      return Routes.profile;
    }

    return null;
  },
  routes: [
    // Splash Screen
    GoRoute(
      path: Routes.splash,
      builder: (context, state) => const SplashPage(),
    ),

    // Login
    GoRoute(
      path: Routes.login,
      builder: (context, state) => const LoginPage(),
    ),

    // ==================== 3-TAB NAVIGATION ====================

    // Tab 1: Chat (对话)
    GoRoute(
      path: Routes.conversation,
      pageBuilder: (context, state) => const NoTransitionPage(
        child: MainShell(child: ConversationPage(), initialIndex: 0),
      ),
    ),

    // Tab 2: Kanban (看板)
    GoRoute(
      path: Routes.kanban,
      pageBuilder: (context, state) => const NoTransitionPage(
        child: MainShell(child: CuratedTimelinePage(), initialIndex: 1),
      ),
    ),

    // Tab 3: Profile (我的)
    GoRoute(
      path: Routes.profile,
      pageBuilder: (context, state) => const NoTransitionPage(
        child: MainShell(child: ProfilePage(), initialIndex: 2),
      ),
    ),

    // Graph (non-tab, accessible from chat)
    GoRoute(
      path: Routes.insightGraph,
      pageBuilder: (context, state) => const CupertinoPage(
        child: InsightGraphPage(),
      ),
    ),

    // ==================== LEGACY ROUTE REDIRECTS ====================

    GoRoute(
      path: Routes.dashboard,
      redirect: (context, state) => Routes.conversation,
    ),
    GoRoute(
      path: Routes.schedule,
      redirect: (context, state) => Routes.kanban,
    ),
    GoRoute(
      path: Routes.timeline,
      redirect: (context, state) => Routes.kanban,
    ),
    GoRoute(
      path: Routes.assistant,
      redirect: (context, state) => Routes.conversation,
    ),
    GoRoute(
      path: Routes.socialLedger,
      redirect: (context, state) => Routes.insightGraph,
    ),
    GoRoute(
      path: Routes.family,
      redirect: (context, state) => Routes.profile,
    ),
    // Legacy /travel redirect to /trips
    GoRoute(
      path: Routes.travel,
      redirect: (context, state) => Routes.trips,
    ),
    // /chat alias for /conversation
    GoRoute(
      path: '/chat',
      redirect: (context, state) => Routes.conversation,
    ),

    // Kanban event detail
    GoRoute(
      path: '/kanban/event/:eventId',
      pageBuilder: (context, state) {
        final event = state.extra as KanbanEventModel?;
        final eventId = state.pathParameters['eventId'] ?? '';
        return CupertinoPage(
          child: EventDetailPage(event: event, eventId: eventId),
        );
      },
    ),

    // Trip memory page (回忆详情页)
    GoRoute(
      path: Routes.tripMemory,
      pageBuilder: (context, state) {
        final story = state.extra as StoryGroup?;
        if (story == null) {
          return const CupertinoPage(
            child: Scaffold(
              body: Center(child: Text('\u6545\u4E8B\u4E0D\u5B58\u5728')),
            ),
          );
        }
        return CupertinoPage(
          child: TripMemoryPage(story: story),
        );
      },
    ),

    // ==================== DEEP LINK ROUTES ====================

    // /event/:id deep link
    GoRoute(
      path: '/event/:id',
      pageBuilder: (context, state) {
        final id = state.pathParameters['id']!;
        return CupertinoPage(
          child: DateDetailPage(dateId: id),
        );
      },
    ),
    // /gift/:id deep link
    GoRoute(
      path: '/gift/:id',
      redirect: (context, state) {
        final id = state.pathParameters['id']!;
        return '${Routes.gifts}/recommend/$id';
      },
    ),

    // ==================== PROFILE SUB-PAGES ====================

    GoRoute(
      path: Routes.smartServices,
      pageBuilder: (context, state) => const CupertinoPage(
        child: SmartServicesPage(),
      ),
    ),
    GoRoute(
      path: Routes.appSettings,
      pageBuilder: (context, state) => const CupertinoPage(
        child: AppSettingsPage(),
      ),
    ),
    GoRoute(
      path: Routes.privacySecurity,
      pageBuilder: (context, state) => const CupertinoPage(
        child: PrivacySecurityPage(),
      ),
    ),
    GoRoute(
      path: Routes.dataBackup,
      pageBuilder: (context, state) => const CupertinoPage(
        child: DataBackupPage(),
      ),
    ),
    GoRoute(
      path: Routes.helpFeedback,
      pageBuilder: (context, state) => const CupertinoPage(
        child: HelpFeedbackPage(),
      ),
    ),
    GoRoute(
      path: Routes.about,
      pageBuilder: (context, state) => const CupertinoPage(
        child: AboutPage(),
      ),
    ),
    GoRoute(
      path: Routes.activityTimeline,
      pageBuilder: (context, state) => const CupertinoPage(
        child: ActivityTimelinePage(),
      ),
    ),
    GoRoute(
      path: Routes.workReport,
      pageBuilder: (context, state) => const CupertinoPage(
        child: WorkReportPage(),
      ),
    ),
    GoRoute(
      path: '/profile/work-report/curation/:jobId',
      pageBuilder: (context, state) {
        final jobId = state.pathParameters['jobId']!;
        return CupertinoPage(
          child: CurationDetailPage(jobId: jobId),
        );
      },
    ),
    GoRoute(
      path: Routes.familyMembers,
      pageBuilder: (context, state) {
        final filter = state.uri.queryParameters['filter'];
        return CupertinoPage(
          child: MembersPage(initialFilter: filter),
        );
      },
    ),
    GoRoute(
      path: Routes.insightHistory,
      pageBuilder: (context, state) => const CupertinoPage(
        child: InsightHistoryPage(),
      ),
    ),
    GoRoute(
      path: Routes.insightSettings,
      pageBuilder: (context, state) => const CupertinoPage(
        child: InsightSettingsPage(),
      ),
    ),

    // Connections
    GoRoute(
      path: Routes.connections,
      pageBuilder: (context, state) => const CupertinoPage(
        child: ConnectionsPage(),
      ),
    ),
    GoRoute(
      path: '/profile/connections/:id',
      pageBuilder: (context, state) {
        final id = state.pathParameters['id']!;
        final connection = state.extra as UserConnection?;
        return CupertinoPage(
          child: ConnectionDetailPage(
            connectionId: id,
            connection: connection,
          ),
        );
      },
    ),

    // Memory browser
    GoRoute(
      path: Routes.memories,
      pageBuilder: (context, state) => const CupertinoPage(
        child: MemoryBrowserPage(),
      ),
    ),
    GoRoute(
      path: '/profile/memories/:memoryId',
      pageBuilder: (context, state) {
        final memoryId = state.pathParameters['memoryId']!;
        final memory = state.extra as MemoryItem?;
        return CupertinoPage(
          child: MemoryDetailPage(
            memoryId: memoryId,
            memory: memory,
          ),
        );
      },
    ),

    // Account settings routes
    GoRoute(
      path: Routes.editProfile,
      pageBuilder: (context, state) => const CupertinoPage(
        child: EditProfilePage(),
      ),
    ),
    GoRoute(
      path: Routes.changePassword,
      pageBuilder: (context, state) => const CupertinoPage(
        child: ChangePasswordPage(),
      ),
    ),
    GoRoute(
      path: Routes.deleteAccount,
      pageBuilder: (context, state) => const CupertinoPage(
        child: DeleteAccountPage(),
      ),
    ),

    GoRoute(
      path: '/profile/services/:serviceId',
      pageBuilder: (context, state) {
        final serviceId = state.pathParameters['serviceId']!;
        final service = state.extra as SmartService?;
        if (service != null) {
          return CupertinoPage(
            child: ServiceDetailPage(service: service),
          );
        }
        return CupertinoPage(
          child: ServiceDetailPage(
            service: SmartService(
              id: serviceId,
              displayName: '服务详情',
              description: '',
              icon: 'settings',
              category: ServiceCategory.other,
              isEnabled: true,
              isRunning: true,
            ),
          ),
        );
      },
    ),

    // ==================== MEMBER SUB-PAGES ====================

    GoRoute(
      path: Routes.memberForm,
      pageBuilder: (context, state) {
        final memberId = state.uri.queryParameters['id'];
        return CupertinoPage(
          child: MemberFormPage(memberId: memberId),
        );
      },
    ),
    GoRoute(
      path: '${Routes.members}/:id',
      pageBuilder: (context, state) {
        final id = state.pathParameters['id']!;
        return CupertinoPage(
          child: MemberDetailPage(memberId: id),
        );
      },
    ),
    GoRoute(
      path: '${Routes.members}/edit/:id',
      pageBuilder: (context, state) {
        final id = state.pathParameters['id']!;
        return CupertinoPage(
          child: MemberFormPage(memberId: id),
        );
      },
    ),
    GoRoute(
      path: '${Routes.members}/:memberId/work-history/add',
      pageBuilder: (context, state) {
        final memberId = state.pathParameters['memberId']!;
        return CupertinoPage(
          child: WorkHistoryFormPage(memberId: memberId),
        );
      },
    ),
    GoRoute(
      path: '${Routes.members}/:memberId/work-history/:workHistoryId/edit',
      pageBuilder: (context, state) {
        final memberId = state.pathParameters['memberId']!;
        final workHistoryId = state.pathParameters['workHistoryId']!;
        return CupertinoPage(
          child: WorkHistoryFormPage(
            memberId: memberId,
            workHistoryId: workHistoryId,
          ),
        );
      },
    ),
    GoRoute(
      path: '${Routes.members}/:memberId/professional-relations/add',
      pageBuilder: (context, state) {
        final memberId = state.pathParameters['memberId']!;
        return CupertinoPage(
          child: ProfessionalRelationFormPage(memberId: memberId),
        );
      },
    ),
    GoRoute(
      path: '${Routes.members}/:memberId/professional-relations/:relationId/edit',
      pageBuilder: (context, state) {
        final memberId = state.pathParameters['memberId']!;
        final relationId = state.pathParameters['relationId']!;
        return CupertinoPage(
          child: ProfessionalRelationFormPage(
            memberId: memberId,
            relationId: relationId,
          ),
        );
      },
    ),

    // ==================== GIFT PAGES ====================

    GoRoute(
      path: Routes.gifts,
      pageBuilder: (context, state) => CupertinoPage(
        child: BlocProvider(
          create: (context) => getIt<GiftsBloc>()..add(const GiftsLoadRequested()),
          child: const GiftsPage(),
        ),
      ),
    ),
    GoRoute(
      path: Routes.giftEntry,
      pageBuilder: (context, state) => const CupertinoPage(
        child: GiftEntryPage(),
      ),
    ),
    GoRoute(
      path: '${Routes.gifts}/recommend/:memberId',
      pageBuilder: (context, state) {
        final memberId = state.pathParameters['memberId']!;
        final occasion = state.uri.queryParameters['occasion'];
        return CupertinoPage(
          child: GiftRecommendationPage(
            memberId: memberId,
            initialOccasion: occasion,
          ),
        );
      },
    ),

    // ==================== DATE PAGES ====================

    GoRoute(
      path: Routes.dates,
      pageBuilder: (context, state) => const CupertinoPage(
        child: DatesPage(),
      ),
      routes: [
        GoRoute(
          path: ':id',
          pageBuilder: (context, state) {
            final id = state.pathParameters['id']!;
            return CupertinoPage(
              child: DateDetailPage(dateId: id),
            );
          },
        ),
      ],
    ),

    // ==================== TRIP PAGES ====================

    GoRoute(
      path: Routes.trips,
      pageBuilder: (context, state) => const CupertinoPage(
        child: TripPage(),
      ),
    ),
    GoRoute(
      path: Routes.tripCreate,
      pageBuilder: (context, state) => const CupertinoPage(
        child: CreateTripPage(),
      ),
    ),
    GoRoute(
      path: Routes.tripRecommend,
      pageBuilder: (context, state) => const CupertinoPage(
        child: DestinationRecommendationPage(),
      ),
    ),
    GoRoute(
      path: '/trips/:tripId',
      pageBuilder: (context, state) {
        final tripId = state.pathParameters['tripId']!;
        return CupertinoPage(
          child: TripDetailPage(tripId: tripId),
        );
      },
      routes: [
        GoRoute(
          path: 'edit',
          pageBuilder: (context, state) {
            final tripId = state.pathParameters['tripId']!;
            return CupertinoPage(
              child: CreateTripPage(tripId: tripId),
            );
          },
        ),
        GoRoute(
          path: 'expense/add',
          pageBuilder: (context, state) {
            final tripId = state.pathParameters['tripId']!;
            return CupertinoPage(
              child: AddExpensePage(tripId: tripId),
            );
          },
        ),
        GoRoute(
          path: 'memories',
          pageBuilder: (context, state) {
            final tripId = state.pathParameters['tripId']!;
            final extra = state.extra as Map<String, dynamic>?;
            final tripName = extra?['tripName'] as String?;
            return CupertinoPage(
              child: MemoryGalleryPage(tripId: tripId, tripName: tripName),
            );
          },
        ),
        GoRoute(
          path: 'feedback',
          pageBuilder: (context, state) {
            final tripId = state.pathParameters['tripId']!;
            final extra = state.extra as Map<String, dynamic>?;
            final tripName = extra?['tripName'] as String?;
            return CupertinoPage(
              child: TripFeedbackPage(tripId: tripId, tripName: tripName),
            );
          },
        ),
      ],
    ),

    // ==================== RELATIONSHIPS PAGES ====================

    GoRoute(
      path: Routes.relationships,
      pageBuilder: (context, state) => CupertinoPage(
        child: BlocProvider(
          create: (context) => getIt<RelationshipsBloc>(),
          child: const RelationshipsPage(),
        ),
      ),
    ),
    GoRoute(
      path: Routes.relationshipGraph,
      pageBuilder: (context, state) => const CupertinoPage(
        child: RelationshipGraphPage(),
      ),
    ),
    GoRoute(
      path: Routes.favorLedger,
      pageBuilder: (context, state) => const CupertinoPage(
        child: FavorLedgerPage(),
      ),
    ),
    GoRoute(
      path: Routes.smartGroups,
      pageBuilder: (context, state) => const CupertinoPage(
        child: SmartGroupsPage(),
      ),
    ),
  ],

  // Error page
  errorBuilder: (context, state) => Scaffold(
    body: Center(
      child: Text('Page not found: ${state.uri}'),
    ),
  ),
);
