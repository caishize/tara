/// Application route paths
class Routes {
  Routes._();

  // Auth
  static const String splash = '/';
  static const String login = '/login';

  // Main tabs (3-tab navigation)
  static const String conversation = '/conversation';  // Tab 1: 对话 (Chat)
  static const String kanban = '/kanban';              // Tab 2: 时光轴 (Timeline)
  static const String profile = '/profile';            // Tab 3: 我的 (Profile)

  // Non-tab routes
  static const String insightGraph = '/insight-graph'; // 图谱 (accessed from chat)

  // Legacy routes (redirect to new tabs)
  static const String dashboard = '/dashboard';        // -> conversation
  static const String schedule = '/schedule';          // -> kanban
  static const String timeline = '/timeline';          // -> kanban
  static const String members = '/members';            // -> graph
  static const String socialLedger = '/social-ledger'; // -> graph
  static const String family = '/family';              // -> profile
  static const String assistant = '/assistant';        // -> conversation
  static const String settings = '/settings';          // -> profile

  // Member routes
  static const String memberForm = '/member/form';
  static String memberDetail(String id) => '/members/$id';
  static String memberEdit(String id) => '/members/edit/$id';

  /// Member list with optional filter
  static String memberList({String? filter}) {
    if (filter != null) {
      return '/profile/members?filter=$filter';
    }
    return '/profile/members';
  }

  // Work History routes
  static String workHistoryAdd(String memberId) => '/members/$memberId/work-history/add';
  static String workHistoryEdit(String memberId, String workHistoryId) =>
      '/members/$memberId/work-history/$workHistoryId/edit';

  // Professional Relation routes
  static String professionalRelationAdd(String memberId) =>
      '/members/$memberId/professional-relations/add';
  static String professionalRelationEdit(String memberId, String relationId) =>
      '/members/$memberId/professional-relations/$relationId/edit';

  // Date routes
  static const String dates = '/dates';
  static String dateDetail(String id) => '/dates/$id';

  // Gift routes
  static const String gifts = '/discover';
  static const String giftEntry = '/gifts/entry';
  static String giftRecommend(String memberId, {String? occasion}) {
    final base = '/discover/recommend/$memberId';
    if (occasion != null) {
      return '$base?occasion=$occasion';
    }
    return base;
  }

  // Profile sub-pages (under /profile)
  static const String smartServices = '/profile/services';
  static const String appSettings = '/profile/app';
  static const String privacySecurity = '/profile/privacy';
  static const String dataBackup = '/profile/backup';
  static const String helpFeedback = '/profile/help';
  static const String about = '/profile/about';
  static const String activityTimeline = '/profile/activity';
  static const String familyMembers = '/profile/members';
  static String serviceDetail(String serviceId) => '/profile/services/$serviceId';

  // Work report
  static const String workReport = '/profile/work-report';
  static String curationJobDetail(String jobId) => '/profile/work-report/curation/$jobId';

  // Connections
  static const String connections = '/profile/connections';
  static String connectionDetail(String id) => '/profile/connections/$id';

  // Memory browser
  static const String memories = '/profile/memories';
  static String memoryDetail(String id) => '/profile/memories/$id';

  // Insight history & settings
  static const String insightHistory = '/profile/insight-history';
  static const String insightSettings = '/profile/insights';

  // Account settings
  static const String editProfile = '/profile/account/edit';
  static const String changePassword = '/profile/account/password';
  static const String deleteAccount = '/profile/account/delete';

  // Trip routes
  static const String trips = '/trips';
  static const String tripCreate = '/trips/create';
  static const String tripRecommend = '/trips/recommend';
  static String tripDetail(String id) => '/trips/$id';
  static String tripEdit(String id) => '/trips/$id/edit';
  static String tripExpenseAdd(String tripId) => '/trips/$tripId/expense/add';
  static String tripMemories(String tripId) => '/trips/$tripId/memories';
  static String tripFeedback(String tripId) => '/trips/$tripId/feedback';

  // Legacy travel routes (redirect to trips)
  static const String travel = '/travel';

  // Kanban event detail
  static String eventDetail(String id) => '/kanban/event/$id';

  // Trip memory (回忆详情页) — narrative view for past trips
  static const String tripMemory = '/kanban/trip-memory';

  // Deep link routes
  static const String chat = '/chat';                     // -> conversation
  static String eventDeepLink(String id) => '/event/$id'; // -> date detail
  static String giftDeepLink(String id) => '/gift/$id';   // -> gift recommend

  // Daily Briefing routes
  static const String dailyBriefing = '/daily-briefing';

  // Guardian/exploration (legacy, redirects to trips)
  static const String tripExploration = '/trips/explore';

  // Relationships routes
  static const String relationships = '/relationships';
  static const String relationshipGraph = '/relationships/graph';
  static const String favorLedger = '/relationships/favors';
  static const String smartGroups = '/relationships/groups';
}
