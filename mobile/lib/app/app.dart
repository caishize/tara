import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:go_router/go_router.dart';

import 'router/app_router.dart';
import 'router/routes.dart';
import 'theme/app_theme.dart';
import 'di/injection.dart';
import '../core/storage/auth_storage.dart';
import '../features/auth/presentation/bloc/auth_bloc.dart';
import '../features/members/presentation/bloc/members_bloc.dart';
import '../features/dates/presentation/bloc/dates_bloc.dart';
import '../features/gifts/presentation/bloc/gifts_bloc.dart';
import '../features/chat/presentation/bloc/assistant_bloc.dart';
import '../features/trip/presentation/bloc/trip_bloc.dart';

class FamilySecretaryApp extends StatefulWidget {
  const FamilySecretaryApp({super.key});

  @override
  State<FamilySecretaryApp> createState() => _FamilySecretaryAppState();
}

class _FamilySecretaryAppState extends State<FamilySecretaryApp> {
  late final GoRouter _router;
  late final AuthStorage _authStorage;

  @override
  void initState() {
    super.initState();
    _authStorage = getIt<AuthStorage>();
    _router = createAppRouter(_authStorage);

    // Listen for auth state changes (e.g., 401 errors triggering logout)
    _authStorage.authStateStream.listen((isAuthenticated) {
      if (!isAuthenticated) {
        _router.go(Routes.login);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider<AuthBloc>(
          create: (_) => getIt<AuthBloc>()..add(const AuthCheckRequested()),
        ),
        BlocProvider<MembersBloc>(
          create: (_) => getIt<MembersBloc>(),
        ),
        BlocProvider<DatesBloc>(
          create: (_) => getIt<DatesBloc>(),
        ),
        BlocProvider<GiftsBloc>(
          create: (_) => getIt<GiftsBloc>(),
        ),
        BlocProvider<AssistantBloc>(
          create: (_) => getIt<AssistantBloc>(),
        ),
        BlocProvider<TripBloc>(
          create: (_) => getIt<TripBloc>(),
        ),
      ],
      child: MaterialApp.router(
        title: '家庭管家',
        debugShowCheckedModeBanner: false,

        // Localization - Chinese support
        localizationsDelegates: const [
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: const [
          Locale('zh', 'CN'),
          Locale('en', 'US'),
        ],
        locale: const Locale('zh', 'CN'),

        // Theme
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,

        // Router
        routerConfig: _router,
      ),
    );
  }
}
