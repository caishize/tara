import 'package:get_it/get_it.dart';
import 'package:dio/dio.dart';
import 'package:hive/hive.dart';

import '../../core/network/api_client.dart';
import '../../core/network/auth_interceptor.dart';
import '../../core/network/websocket_service.dart';
import '../../core/notifications/push_notification_service.dart';
import '../../core/storage/local_storage.dart';
import '../../core/storage/auth_storage.dart';
import '../../core/storage/settings_storage.dart';
import '../../core/config/app_config.dart';
import '../../core/location/location_service.dart';

// Feature imports — auth
import '../../features/auth/data/datasources/auth_remote_datasource.dart';
import '../../features/auth/data/repositories/auth_repository_impl.dart';
import '../../features/auth/domain/repositories/auth_repository.dart';
import '../../features/auth/domain/usecases/login_usecase.dart';
import '../../features/auth/presentation/bloc/auth_bloc.dart';

// Feature imports — members
import '../../features/members/data/datasources/member_remote_datasource.dart';
import '../../features/members/data/datasources/member_local_datasource.dart';
import '../../features/members/data/repositories/member_repository_impl.dart';
import '../../features/members/domain/repositories/member_repository.dart';
import '../../features/members/domain/usecases/get_members_usecase.dart';
import '../../features/members/domain/usecases/create_member_usecase.dart';
import '../../features/members/presentation/bloc/members_bloc.dart';

// Feature imports — dates
import '../../features/dates/data/datasources/date_remote_datasource.dart';
import '../../features/dates/data/repositories/date_repository_impl.dart';
import '../../features/dates/domain/repositories/date_repository.dart';
import '../../features/dates/domain/usecases/get_dates_usecase.dart';
import '../../features/dates/presentation/bloc/dates_bloc.dart';

// Feature imports — gifts
import '../../features/gifts/data/datasources/gift_remote_datasource.dart';
import '../../features/gifts/data/repositories/gift_repository_impl.dart';
import '../../features/gifts/domain/repositories/gift_repository.dart';
import '../../features/gifts/presentation/bloc/gifts_bloc.dart';

// Feature imports — chat (was assistant + secretary)
import '../../features/chat/data/datasources/assistant_remote_datasource.dart';
import '../../features/chat/data/datasources/pending_action_datasource.dart';
import '../../features/chat/data/repositories/assistant_repository_impl.dart';
import '../../features/chat/domain/repositories/assistant_repository.dart';
import '../../features/chat/presentation/bloc/assistant_bloc.dart';
import '../../features/chat/data/datasources/briefing_remote_datasource.dart';
import '../../features/chat/data/repositories/briefing_repository_impl.dart';
import '../../features/chat/domain/repositories/briefing_repository.dart';
import '../../features/chat/presentation/bloc/daily_briefing_bloc.dart';

// Feature imports — trip (was travel)
import '../../features/trip/data/datasources/trip_remote_datasource.dart';
import '../../features/trip/data/repositories/trip_repository_impl.dart';
import '../../features/trip/domain/repositories/trip_repository.dart';
import '../../features/trip/presentation/bloc/trip_bloc.dart';

// Feature imports — profile
import '../../features/profile/data/datasources/profile_remote_datasource.dart';
import '../../features/profile/data/repositories/profile_repository_impl.dart';
import '../../features/profile/data/repositories/settings_repository_impl.dart';
import '../../features/profile/domain/repositories/profile_repository.dart';
import '../../features/profile/domain/repositories/settings_repository.dart';
import '../../features/profile/presentation/bloc/profile_bloc.dart';
import '../../features/profile/presentation/bloc/settings_bloc.dart';
import '../../features/profile/presentation/bloc/service_detail_bloc.dart';
import '../../features/profile/presentation/bloc/activity_bloc.dart';
import '../../features/profile/presentation/bloc/work_report_bloc.dart';
import '../../features/profile/data/datasources/connections_remote_datasource.dart';
import '../../features/profile/data/datasources/memory_browser_remote_datasource.dart';
import '../../features/profile/presentation/bloc/connections_bloc.dart';
import '../../features/profile/presentation/bloc/memory_browser_bloc.dart';
import '../../features/profile/presentation/bloc/insight_history_bloc.dart';

// Feature imports — relationships
import '../../features/relationships/data/datasources/relationship_remote_datasource.dart';
import '../../features/relationships/data/repositories/relationship_repository_impl.dart';
import '../../features/relationships/domain/repositories/relationship_repository.dart';
import '../../features/relationships/presentation/bloc/relationships_bloc.dart';

// Feature imports — graph (merged into kanban)
import '../../features/kanban/data/datasources/insight_graph_remote_datasource.dart';
import '../../features/kanban/data/repositories/insight_graph_repository_impl.dart';
import '../../features/kanban/domain/repositories/insight_graph_repository.dart';
import '../../features/kanban/presentation/bloc/insight_graph_bloc.dart';

// Feature imports — kanban (was timeline + schedule)
import '../../features/kanban/data/datasources/curated_timeline_datasource.dart';
import '../../features/kanban/data/datasources/insight_feed_datasource.dart';
import '../../features/kanban/data/datasources/event_search_datasource.dart';
import '../../features/kanban/data/repositories/curated_timeline_repository_impl.dart';
import '../../features/kanban/data/repositories/insight_feed_repository_impl.dart';
import '../../features/kanban/domain/repositories/curated_timeline_repository.dart';
import '../../features/kanban/domain/repositories/insight_feed_repository.dart';
import '../../features/kanban/presentation/bloc/curated_timeline_bloc.dart';
import '../../features/kanban/presentation/bloc/future_view_bloc.dart';
import '../../features/kanban/presentation/bloc/insight_feed_bloc.dart';
import '../../features/kanban/presentation/bloc/kanban_bloc.dart';
import '../../features/kanban/presentation/bloc/memory_lane_bloc.dart';
import '../../features/kanban/data/datasources/schedule_aggregator.dart';
import '../../features/kanban/data/repositories/schedule_repository_impl.dart';
import '../../features/kanban/domain/repositories/schedule_repository.dart';
import '../../features/kanban/presentation/bloc/schedule_bloc.dart';

final getIt = GetIt.instance;

Future<void> configureDependencies() async {
  // Core
  await _registerCore();

  // Features
  _registerAuthFeature();
  _registerMembersFeature();
  _registerDatesFeature();
  _registerGiftsFeature();
  _registerChatFeature();
  _registerTripFeature();
  _registerProfileFeature();
  _registerRelationshipsFeature();
  _registerGraphFeature();
  _registerKanbanFeature();
}

Future<void> _registerCore() async {
  // Local Storage
  final authBox = await Hive.openBox('auth');
  final cacheBox = await Hive.openBox('cache');
  final settingsBox = await Hive.openBox('settings');

  getIt.registerSingleton<LocalStorage>(LocalStorage(cacheBox));
  final authStorage = AuthStorage(authBox);
  await authStorage.initialize();
  getIt.registerSingleton<AuthStorage>(authStorage);
  getIt.registerSingleton<SettingsStorage>(SettingsStorage(settingsBox));

  // Network
  const baseUrl = AppConfig.apiBaseUrl;
  final dio = Dio(BaseOptions(
    baseUrl: baseUrl,
    connectTimeout: const Duration(seconds: 30),
    receiveTimeout: const Duration(minutes: 10),
    sendTimeout: const Duration(seconds: 30),
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  ));

  dio.interceptors.add(AuthInterceptor(getIt<AuthStorage>()));
  dio.interceptors.add(LogInterceptor(
    requestBody: true,
    responseBody: true,
  ));

  getIt.registerSingleton<Dio>(dio);
  getIt.registerSingleton<ApiClient>(ApiClient(dio));

  // WebSocket Service
  getIt.registerSingleton<WebSocketService>(
    WebSocketService(getIt<AuthStorage>(), baseUrl),
  );

  // Location Service
  getIt.registerLazySingleton<LocationService>(() => LocationService());

  // Push Notification Service
  getIt.registerSingleton<PushNotificationService>(
    PushNotificationService(
      apiClient: getIt<ApiClient>(),
      authStorage: getIt<AuthStorage>(),
    ),
  );
}

void _registerAuthFeature() {
  getIt.registerLazySingleton<AuthRemoteDataSource>(
    () => AuthRemoteDataSource(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<AuthRepository>(
    () => AuthRepositoryImpl(
      remoteDataSource: getIt<AuthRemoteDataSource>(),
      authStorage: getIt<AuthStorage>(),
    ),
  );
  getIt.registerLazySingleton(() => LoginUseCase(getIt<AuthRepository>()));
  getIt.registerFactory<AuthBloc>(
    () => AuthBloc(
      loginUseCase: getIt<LoginUseCase>(),
      authStorage: getIt<AuthStorage>(),
      authRepository: getIt<AuthRepository>(),
    ),
  );
}

void _registerMembersFeature() {
  getIt.registerLazySingleton<MemberRemoteDataSource>(
    () => MemberRemoteDataSource(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<MemberLocalDataSource>(
    () => MemberLocalDataSource(getIt<LocalStorage>()),
  );
  getIt.registerLazySingleton<MemberRepository>(
    () => MemberRepositoryImpl(
      remoteDataSource: getIt<MemberRemoteDataSource>(),
      localDataSource: getIt<MemberLocalDataSource>(),
    ),
  );
  getIt.registerLazySingleton(() => GetMembersUseCase(getIt<MemberRepository>()));
  getIt.registerLazySingleton(() => CreateMemberUseCase(getIt<MemberRepository>()));
  getIt.registerFactory<MembersBloc>(
    () => MembersBloc(
      getMembersUseCase: getIt<GetMembersUseCase>(),
      createMemberUseCase: getIt<CreateMemberUseCase>(),
      repository: getIt<MemberRepository>(),
    ),
  );
}

void _registerDatesFeature() {
  getIt.registerLazySingleton<DateRemoteDataSource>(
    () => DateRemoteDataSource(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<DateRepository>(
    () => DateRepositoryImpl(
      remoteDataSource: getIt<DateRemoteDataSource>(),
    ),
  );
  getIt.registerLazySingleton(() => GetDatesUseCase(getIt<DateRepository>()));
  getIt.registerLazySingleton(() => GetUpcomingDatesUseCase(getIt<DateRepository>()));
  getIt.registerLazySingleton(() => CreateDateUseCase(getIt<DateRepository>()));
  getIt.registerLazySingleton(() => UpdateDateUseCase(getIt<DateRepository>()));
  getIt.registerLazySingleton(() => DeleteDateUseCase(getIt<DateRepository>()));
  getIt.registerFactory<DatesBloc>(
    () => DatesBloc(
      getDatesUseCase: getIt<GetDatesUseCase>(),
      getUpcomingDatesUseCase: getIt<GetUpcomingDatesUseCase>(),
      createDateUseCase: getIt<CreateDateUseCase>(),
      updateDateUseCase: getIt<UpdateDateUseCase>(),
      deleteDateUseCase: getIt<DeleteDateUseCase>(),
    ),
  );
}

void _registerGiftsFeature() {
  getIt.registerLazySingleton<GiftRemoteDataSource>(
    () => GiftRemoteDataSource(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<GiftRepository>(
    () => GiftRepositoryImpl(
      remoteDataSource: getIt<GiftRemoteDataSource>(),
    ),
  );
  getIt.registerFactory<GiftsBloc>(
    () => GiftsBloc(repository: getIt<GiftRepository>()),
  );
}

void _registerChatFeature() {
  // Assistant (AI chat) data layer
  final assistantDio = Dio(BaseOptions(
    baseUrl: AppConfig.apiBaseUrl,
    connectTimeout: const Duration(seconds: 30),
    receiveTimeout: const Duration(minutes: 10),
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  ));
  assistantDio.interceptors.add(AuthInterceptor(getIt<AuthStorage>()));

  getIt.registerLazySingleton<AssistantRemoteDataSource>(
    () => AssistantRemoteDataSourceImpl(
      apiClient: getIt<ApiClient>(),
      dio: assistantDio,
      webSocketService: getIt<WebSocketService>(),
    ),
  );
  getIt.registerLazySingleton<PendingActionDatasource>(
    () => PendingActionDatasource(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<AssistantRepository>(
    () => AssistantRepositoryImpl(
      remoteDataSource: getIt<AssistantRemoteDataSource>(),
    ),
  );
  getIt.registerFactory<AssistantBloc>(
    () => AssistantBloc(
      repository: getIt<AssistantRepository>(),
      pendingActionDatasource: getIt<PendingActionDatasource>(),
      locationService: getIt<LocationService>(),
      webSocketService: getIt<WebSocketService>(),
    ),
  );

  // Briefing (daily briefing) data layer — was secretary feature
  getIt.registerLazySingleton<BriefingRemoteDataSource>(
    () => BriefingRemoteDataSourceImpl(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<SecretaryRepository>(
    () => SecretaryRepositoryImpl(
      getIt<BriefingRemoteDataSource>(),
      getIt<ApiClient>(),
    ),
  );
  getIt.registerLazySingleton<DailyBriefingBloc>(
    () => DailyBriefingBloc(getIt<SecretaryRepository>()),
  );
}

void _registerTripFeature() {
  getIt.registerLazySingleton<TripRemoteDataSource>(
    () => TripRemoteDataSourceImpl(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<TripRepository>(
    () => TripRepositoryImpl(
      remoteDataSource: getIt<TripRemoteDataSource>(),
    ),
  );
  getIt.registerFactory<TripBloc>(
    () => TripBloc(repository: getIt<TripRepository>()),
  );
}

void _registerProfileFeature() {
  getIt.registerLazySingleton<ProfileRemoteDataSource>(
    () => ProfileRemoteDataSource(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<ProfileRepository>(
    () => ProfileRepositoryImpl(
      remoteDataSource: getIt<ProfileRemoteDataSource>(),
    ),
  );
  getIt.registerLazySingleton<SettingsRepository>(
    () => SettingsRepositoryImpl(
      storage: getIt<SettingsStorage>(),
      remoteDataSource: getIt<ProfileRemoteDataSource>(),
    ),
  );
  getIt.registerFactory<ProfileBloc>(
    () => ProfileBloc(
      repository: getIt<ProfileRepository>(),
      remoteDataSource: getIt<ProfileRemoteDataSource>(),
    ),
  );
  getIt.registerFactory<SettingsBloc>(
    () => SettingsBloc(repository: getIt<SettingsRepository>()),
  );
  getIt.registerFactory<ServiceDetailBloc>(
    () => ServiceDetailBloc(getIt<ProfileRemoteDataSource>()),
  );
  getIt.registerFactory<ActivityBloc>(
    () => ActivityBloc(getIt<ProfileRemoteDataSource>()),
  );
  getIt.registerFactory<WorkReportBloc>(
    () => WorkReportBloc(getIt<ProfileRemoteDataSource>()),
  );

  // Connections
  getIt.registerLazySingleton<ConnectionsRemoteDataSource>(
    () => ConnectionsRemoteDataSource(getIt<ApiClient>()),
  );
  getIt.registerFactory<ConnectionsBloc>(
    () => ConnectionsBloc(dataSource: getIt<ConnectionsRemoteDataSource>()),
  );

  // Memory browser
  getIt.registerLazySingleton<MemoryBrowserRemoteDataSource>(
    () => MemoryBrowserRemoteDataSource(getIt<ApiClient>()),
  );
  getIt.registerFactory<MemoryBrowserBloc>(
    () => MemoryBrowserBloc(dataSource: getIt<MemoryBrowserRemoteDataSource>()),
  );

  // Insight history
  getIt.registerFactory<InsightHistoryBloc>(
    () => InsightHistoryBloc(dataSource: getIt<MemoryBrowserRemoteDataSource>()),
  );
}

void _registerRelationshipsFeature() {
  getIt.registerLazySingleton<RelationshipRemoteDataSource>(
    () => RelationshipRemoteDataSource(getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<RelationshipRepository>(
    () => RelationshipRepositoryImpl(
      remoteDataSource: getIt<RelationshipRemoteDataSource>(),
    ),
  );
  getIt.registerFactory<RelationshipsBloc>(
    () => RelationshipsBloc(repository: getIt<RelationshipRepository>()),
  );
}

void _registerGraphFeature() {
  getIt.registerLazySingleton<InsightGraphRemoteDataSource>(
    () => InsightGraphRemoteDataSourceImpl(apiClient: getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<InsightGraphRepository>(
    () => InsightGraphRepositoryImpl(
      remoteDataSource: getIt<InsightGraphRemoteDataSource>(),
    ),
  );
  getIt.registerFactory<InsightGraphBloc>(
    () => InsightGraphBloc(repository: getIt<InsightGraphRepository>()),
  );
}

void _registerKanbanFeature() {
  // Curated timeline data sources
  getIt.registerLazySingleton<CuratedTimelineRemoteDataSource>(
    () => CuratedTimelineRemoteDataSourceImpl(apiClient: getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<CuratedTimelineRepository>(
    () => CuratedTimelineRepositoryImpl(
      remoteDataSource: getIt<CuratedTimelineRemoteDataSource>(),
    ),
  );

  // Insight feed data layer (extracted from curated timeline)
  getIt.registerLazySingleton<InsightFeedRemoteDataSource>(
    () => InsightFeedRemoteDataSourceImpl(apiClient: getIt<ApiClient>()),
  );
  getIt.registerLazySingleton<InsightFeedRepository>(
    () => InsightFeedRepositoryImpl(
      remoteDataSource: getIt<InsightFeedRemoteDataSource>(),
    ),
  );

  // Event search data source (extracted from curated timeline)
  getIt.registerLazySingleton<EventSearchRemoteDataSource>(
    () => EventSearchRemoteDataSourceImpl(apiClient: getIt<ApiClient>()),
  );

  getIt.registerFactory<CuratedTimelineBloc>(
    () => CuratedTimelineBloc(repository: getIt<CuratedTimelineRepository>()),
  );
  getIt.registerFactory<KanbanBloc>(
    () => KanbanBloc(repository: getIt<CuratedTimelineRepository>()),
  );
  getIt.registerFactory<InsightFeedBloc>(
    () => InsightFeedBloc(repository: getIt<InsightFeedRepository>()),
  );
  getIt.registerFactory<FutureViewBloc>(
    () => FutureViewBloc(repository: getIt<InsightFeedRepository>()),
  );
  getIt.registerFactory<MemoryLaneBloc>(
    () => MemoryLaneBloc(
      repository: getIt<CuratedTimelineRepository>(),
      insightFeedRepository: getIt<InsightFeedRepository>(),
    ),
  );

  // Schedule aggregator (uses date/trip/task repositories)
  getIt.registerLazySingleton<ScheduleAggregator>(
    () => ScheduleAggregator(
      dateRepository: getIt<DateRepository>(),
      tripRepository: getIt<TripRepository>(),
    ),
  );
  getIt.registerLazySingleton<ScheduleRepository>(
    () => ScheduleRepositoryImpl(
      aggregator: getIt<ScheduleAggregator>(),
    ),
  );
  getIt.registerLazySingleton<ScheduleBloc>(
    () => ScheduleBloc(
      repository: getIt<ScheduleRepository>(),
      apiClient: getIt<ApiClient>(),
    ),
  );
}
