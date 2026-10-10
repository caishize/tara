import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:firebase_core/firebase_core.dart';

import 'app/app.dart';
import 'app/di/injection.dart';
import 'core/notifications/push_notification_service.dart';
import 'core/utils/bloc_observer.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Hive for local storage
  await Hive.initFlutter();

  // Initialize Firebase (requires firebase_options.dart from flutterfire configure)
  try {
    await Firebase.initializeApp();
  } catch (e) {
    // Firebase not configured yet — push notifications will be disabled
    debugPrint('Firebase init skipped: $e');
  }

  // Configure dependency injection
  await configureDependencies();

  // Initialize push notifications (non-blocking; gracefully degrades)
  try {
    await getIt<PushNotificationService>().initialize();
  } catch (e) {
    debugPrint('Push notification init skipped: $e');
  }

  // Set preferred orientations
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // System UI overlay style is controlled by the theme (light/dark)
  // via AppBarTheme and AnnotatedRegion in individual pages.

  // Set BLoC observer for debugging
  Bloc.observer = AppBlocObserver();

  runApp(const FamilySecretaryApp());
}
