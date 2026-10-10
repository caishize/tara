import 'dart:async';

/// Cross-BLoC event bus using StreamController.broadcast.
///
/// Enables decoupled communication between features without
/// direct BLoC-to-BLoC dependencies.
///
/// Usage:
///   AppEventBus.instance.fire(TripCreatedEvent(tripId: '123'));
///   AppEventBus.instance.on<TripCreatedEvent>().listen((e) { ... });
class AppEventBus {
  static final AppEventBus instance = AppEventBus._();

  final _controller = StreamController<AppEvent>.broadcast();

  AppEventBus._();

  /// Fire an event to all listeners.
  void fire(AppEvent event) {
    _controller.add(event);
  }

  /// Listen for events of a specific type.
  Stream<T> on<T extends AppEvent>() {
    return _controller.stream.where((e) => e is T).cast<T>();
  }

  /// Dispose the event bus (call on app shutdown).
  void dispose() {
    _controller.close();
  }
}

/// Base class for all app events.
abstract class AppEvent {
  const AppEvent();
}

/// Event fired when a trip is created.
class TripCreatedEvent extends AppEvent {
  final String tripId;
  const TripCreatedEvent({required this.tripId});
}

/// Event fired when a trip is updated.
class TripUpdatedEvent extends AppEvent {
  final String tripId;
  const TripUpdatedEvent({required this.tripId});
}

/// Event fired when memory is extracted from conversation.
class MemoryExtractedEvent extends AppEvent {
  final String memoryId;
  const MemoryExtractedEvent({required this.memoryId});
}

/// Event fired when member profile is updated.
class MemberUpdatedEvent extends AppEvent {
  final String memberId;
  const MemberUpdatedEvent({required this.memberId});
}

/// Event fired when kanban view needs refresh.
class KanbanRefreshEvent extends AppEvent {
  const KanbanRefreshEvent();
}

/// Event fired when trip preparation item is toggled (checked/unchecked).
class PreparationToggledEvent extends AppEvent {
  final String tripId;
  final String itemId;
  final bool isCompleted;
  const PreparationToggledEvent({
    required this.tripId,
    required this.itemId,
    required this.isCompleted,
  });
}

/// Event fired when a chat session is cleared/deleted.
class SessionClearedEvent extends AppEvent {
  final String sessionId;
  const SessionClearedEvent({required this.sessionId});
}
