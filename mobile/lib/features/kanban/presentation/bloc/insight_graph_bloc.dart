import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/datasources/insight_graph_remote_datasource.dart';
import '../../data/models/core_event_model.dart';
import '../../domain/entities/associated_item.dart';
import '../../domain/entities/core_event.dart';
import '../../domain/entities/insight_graph_data.dart';
import '../../domain/repositories/insight_graph_repository.dart';
import 'insight_graph_event.dart';
import 'insight_graph_state.dart';

/// 动态图谱 BLoC
class InsightGraphBloc extends Bloc<InsightGraphEvent, InsightGraphState> {
  final InsightGraphRepository _repository;

  /// Race condition workaround: LoadUpcomingTrips and LoadInsightGraph fire
  /// concurrently. If trips resolve first (before state is InsightGraphLoaded),
  /// we buffer them here so _onLoadInsightGraph can merge them into the first
  /// InsightGraphLoaded emission. Consumed once and set back to null.
  /// This lives outside the state machine because BLoC events are processed
  /// sequentially — the buffer is only read by the next queued event handler.
  List<TripSummary>? _pendingTrips;

  InsightGraphBloc({
    required InsightGraphRepository repository,
  })  : _repository = repository,
        super(const InsightGraphInitial()) {
    on<LoadInsightGraph>(_onLoadInsightGraph);
    on<LoadInsightGraphForEvent>(_onLoadInsightGraphForEvent);
    on<RefreshInsightGraph>(_onRefreshInsightGraph);
    on<FilterByType>(_onFilterByType);
    on<DismissItem>(_onDismissItem);
    on<ConfirmItem>(_onConfirmItem);
    on<SnoozeItem>(_onSnoozeItem);
    on<DismissAlert>(_onDismissAlert);
    on<FilterByCategory>(_onFilterByCategory);
    on<ClearFilter>(_onClearFilter);
    on<ResolveConflict>(_onResolveConflict);
    // PRD 2.3.2: 行程切换相关事件
    on<LoadUpcomingTrips>(_onLoadUpcomingTrips);
    on<SwitchTrip>(_onSwitchTrip);
    on<LoadTripGraph>(_onLoadTripGraph);
    on<ExecuteNodeAction>(_onExecuteNodeAction);
  }

  /// 处理加载动态图谱事件
  Future<void> _onLoadInsightGraph(
    LoadInsightGraph event,
    Emitter<InsightGraphState> emit,
  ) async {
    emit(const InsightGraphLoading());

    try {
      final data = await _repository.getInsightGraph(
        targetDate: event.targetDate,
      );

      // Show empty state only if there's no data at all (no core event)
      if (data == null) {
        emit(const InsightGraphEmpty());
        return;
      }

      // Show loaded state even with empty associations (core event will still display)
      // Apply buffered trips if LoadUpcomingTrips resolved before us
      final bufferedTrips = _pendingTrips;
      _pendingTrips = null;

      emit(InsightGraphLoaded(
        data: data,
        filteredItems: data.associatedItems,
        upcomingTrips: bufferedTrips ?? const [],
        selectedTripId: bufferedTrips != null && bufferedTrips.isNotEmpty
            ? bufferedTrips.first.id
            : null,
      ));

      // Auto-load first trip's graph if trips were buffered
      if (bufferedTrips != null && bufferedTrips.isNotEmpty) {
        add(LoadTripGraph(bufferedTrips.first.id));
      }
    } catch (e) {
      emit(InsightGraphError(
        message: '加载失败: ${e.toString()}',
        errorType: InsightGraphErrorType.unknown,
      ));
    }
  }

  /// 处理加载特定事件的动态图谱
  Future<void> _onLoadInsightGraphForEvent(
    LoadInsightGraphForEvent event,
    Emitter<InsightGraphState> emit,
  ) async {
    emit(const InsightGraphLoading());

    try {
      final data = await _repository.getInsightGraphForEvent(event.eventId);

      // Show empty state only if there's no data at all
      if (data == null) {
        emit(const InsightGraphEmpty());
        return;
      }

      // Show loaded state even with empty associations
      emit(InsightGraphLoaded(
        data: data,
        filteredItems: data.associatedItems,
      ));
    } catch (e) {
      emit(InsightGraphError(
        message: '加载失败: ${e.toString()}',
        errorType: InsightGraphErrorType.unknown,
      ));
    }
  }

  /// 处理刷新事件
  Future<void> _onRefreshInsightGraph(
    RefreshInsightGraph event,
    Emitter<InsightGraphState> emit,
  ) async {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      emit(currentState.copyWith(isRefreshing: true));

      try {
        final data = await _repository.getInsightGraph();

        // Show empty state only if there's no data at all
        if (data == null) {
          emit(const InsightGraphEmpty());
          return;
        }

        final filteredItems = _applyFilter(
          data.associatedItems,
          currentState.activeFilter,
        );

        emit(InsightGraphLoaded(
          data: data,
          activeFilter: currentState.activeFilter,
          filteredItems: filteredItems,
        ));
      } catch (e) {
        // 刷新失败时保留原数据
        emit(currentState.copyWith(isRefreshing: false));
      }
    } else {
      // 如果不是已加载状态，则执行完整加载
      add(const LoadInsightGraph());
    }
  }

  /// 处理筛选事件
  void _onFilterByType(
    FilterByType event,
    Emitter<InsightGraphState> emit,
  ) {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      final filteredItems = _applyFilter(
        currentState.data.associatedItems,
        event.type,
      );

      emit(currentState.copyWith(
        activeFilter: event.type,
        filteredItems: filteredItems,
        clearFilter: event.type == null,
      ));
    }
  }

  /// 处理忽略事项事件
  Future<void> _onDismissItem(
    DismissItem event,
    Emitter<InsightGraphState> emit,
  ) async {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      try {
        await _repository.dismissItem(
          event.itemId,
          correction: event.correction,
        );

        // 从本地状态中移除该事项
        final updatedItems = currentState.data.associatedItems
            .where((item) => item.id != event.itemId)
            .toList();

        final updatedData = currentState.data.copyWith(
          associatedItems: updatedItems,
        );

        final filteredItems = _applyFilter(
          updatedItems,
          currentState.activeFilter,
        );

        emit(currentState.copyWith(
          data: updatedData,
          filteredItems: filteredItems,
        ));
      } catch (e) {
        emit(currentState.copyWith(operationError: '忽略操作失败: $e'));
      }
    }
  }

  /// 处理确认事项事件
  Future<void> _onConfirmItem(
    ConfirmItem event,
    Emitter<InsightGraphState> emit,
  ) async {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      try {
        await _repository.confirmItem(
          event.itemId,
          scheduledStart: event.scheduledStart,
        );

        // 从本地状态中移除该事项（已确认）
        final updatedItems = currentState.data.associatedItems
            .where((item) => item.id != event.itemId)
            .toList();

        final updatedData = currentState.data.copyWith(
          associatedItems: updatedItems,
        );

        final filteredItems = _applyFilter(
          updatedItems,
          currentState.activeFilter,
        );

        emit(currentState.copyWith(
          data: updatedData,
          filteredItems: filteredItems,
        ));
      } catch (e) {
        emit(currentState.copyWith(operationError: '确认操作失败: $e'));
      }
    }
  }

  /// 处理延后事项事件
  Future<void> _onSnoozeItem(
    SnoozeItem event,
    Emitter<InsightGraphState> emit,
  ) async {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      try {
        await _repository.snoozeItem(event.itemId, event.duration);

        // 从本地状态中移除该事项（已延后）
        final updatedItems = currentState.data.associatedItems
            .where((item) => item.id != event.itemId)
            .toList();

        final updatedData = currentState.data.copyWith(
          associatedItems: updatedItems,
        );

        final filteredItems = _applyFilter(
          updatedItems,
          currentState.activeFilter,
        );

        emit(currentState.copyWith(
          data: updatedData,
          filteredItems: filteredItems,
        ));
      } catch (e) {
        emit(currentState.copyWith(operationError: '延后操作失败: $e'));
      }
    }
  }

  /// 处理忽略提醒事件
  Future<void> _onDismissAlert(
    DismissAlert event,
    Emitter<InsightGraphState> emit,
  ) async {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      try {
        await _repository.dismissAlert(event.alertId);

        // 从本地状态中移除该提醒
        final updatedAlerts = currentState.data.conflictAlerts
            .where((alert) => alert.id != event.alertId)
            .toList();

        final updatedData = currentState.data.copyWith(
          conflictAlerts: updatedAlerts,
        );

        emit(currentState.copyWith(data: updatedData));
      } catch (e) {
        emit(currentState.copyWith(operationError: '忽略提醒失败: $e'));
      }
    }
  }

  /// 处理冲突解决事件 (确认或拒绝待处理操作)
  Future<void> _onResolveConflict(
    ResolveConflict event,
    Emitter<InsightGraphState> emit,
  ) async {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      try {
        switch (event.action) {
          case ConflictResolutionAction.confirm:
            await _repository.confirmPendingAction(
              event.pendingActionId,
              newStart: event.newStart,
              newEnd: event.newEnd,
            );
          case ConflictResolutionAction.reject:
            await _repository.rejectPendingAction(event.pendingActionId);
        }

        // Remove the alert from local state
        final updatedAlerts = currentState.data.conflictAlerts
            .where((alert) => alert.id != event.alertId)
            .toList();

        final updatedData = currentState.data.copyWith(
          conflictAlerts: updatedAlerts,
        );

        emit(currentState.copyWith(data: updatedData));

        // Re-fetch graph data so event cards reflect updated times
        add(const RefreshInsightGraph());
        add(const LoadUpcomingTrips());
      } catch (e) {
        emit(currentState.copyWith(operationError: '冲突解决失败: $e'));
      }
    }
  }

  /// 按分类筛选关联
  void _onFilterByCategory(
    FilterByCategory event,
    Emitter<InsightGraphState> emit,
  ) {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      final itemType = _categoryToItemType(event.category);
      final filteredItems = _applyCategoryFilter(
        currentState.data.associatedItems,
        event.category,
        itemType,
      );

      emit(currentState.copyWith(
        activeFilter: itemType,
        filteredItems: filteredItems,
      ));
    }
  }

  /// 清除筛选
  void _onClearFilter(
    ClearFilter event,
    Emitter<InsightGraphState> emit,
  ) {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      emit(currentState.copyWith(
        clearFilter: true,
        filteredItems: currentState.data.associatedItems,
      ));
    }
  }

  /// Map category string to ItemType (returns null for categories without direct mapping)
  ItemType? _categoryToItemType(String category) {
    switch (category) {
      case 'person':
        return ItemType.person;
      case 'task':
        return ItemType.task;
      case 'place':
        return ItemType.place;
      case 'gift':
        return ItemType.gift;
      default:
        return null;
    }
  }

  /// Apply category filter - supports both ItemType and metadata-based categories
  List<AssociatedItem> _applyCategoryFilter(
    List<AssociatedItem> items,
    String category,
    ItemType? itemType,
  ) {
    if (itemType != null) {
      return items.where((item) => item.itemType == itemType).toList();
    }
    // For categories like 'memory', 'date', 'history' — filter by metadata
    return items.where((item) {
      final meta = item.metadata;
      if (meta == null) return false;
      final itemCategory = meta['category'] as String?;
      return itemCategory == category;
    }).toList();
  }

  /// 应用筛选条件
  List<AssociatedItem> _applyFilter(
    List<AssociatedItem> items,
    ItemType? filter,
  ) {
    if (filter == null) {
      return items;
    }
    return items.where((item) => item.itemType == filter).toList();
  }

  /// PRD 2.3.2: 加载即将到来的行程列表
  Future<void> _onLoadUpcomingTrips(
    LoadUpcomingTrips event,
    Emitter<InsightGraphState> emit,
  ) async {
    try {
      final trips = await _repository.getUpcomingTrips(limit: 5);
      final currentState = state;

      if (currentState is InsightGraphLoaded) {
        emit(currentState.copyWith(
          upcomingTrips: trips,
          selectedTripId: currentState.selectedTripId ?? (trips.isNotEmpty ? trips.first.id : null),
        ));

        // 自动加载第一个行程的图谱
        if (trips.isNotEmpty && currentState.tripGraph == null) {
          add(LoadTripGraph(trips.first.id));
        }
      } else {
        // State not yet loaded — buffer trips for _onLoadInsightGraph to apply
        _pendingTrips = trips;
      }
    } catch (_) {
      // Trip loading is supplementary — do not block the main graph flow.
      // The UI simply won't show the trip switcher.
    }
  }

  /// PRD 2.3.2: 切换行程
  Future<void> _onSwitchTrip(
    SwitchTrip event,
    Emitter<InsightGraphState> emit,
  ) async {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      // Update selected trip immediately for UI feedback
      emit(currentState.copyWith(
        selectedTripId: event.tripId,
        isRefreshing: true,
      ));

      // Reload insight graph for the selected trip (curated_event.id)
      add(LoadTripGraph(event.tripId));
    }
  }

  /// 执行图谱节点操作
  Future<void> _onExecuteNodeAction(
    ExecuteNodeAction event,
    Emitter<InsightGraphState> emit,
  ) async {
    final currentState = state;
    if (currentState is! InsightGraphLoaded) return;

    switch (event.actionType) {
      case 'confirm':
      case 'mark_done':
        await _handleConfirmAction(event, currentState, emit);
      case 'dismiss':
        await _handleDismissAction(event, currentState, emit);
      case 'send_greeting':
        _handleNavigateToChat(event, currentState, emit, prefill: '你好！');
      case 'view_details':
      case 'view_profile':
        _handleViewDetail(event, currentState, emit);
      case 'set_reminder':
        emit(currentState.copyWith(
          nodeActionResult: NodeActionResult(
            type: NodeActionType.navigate,
            nodeId: event.associationId,
            routePath: '/conversation',
            routeExtra: {'prefill': '帮我创建一个提醒'},
            message: '创建提醒',
          ),
        ));
      case 'schedule_meeting':
        _handleNavigateToChat(event, currentState, emit, prefill: '帮我安排一次会面');
      case 'send_gift':
        _handlePrepareGift(event, currentState, emit);
      case 'snooze':
        await _handleSnoozeAction(event, currentState, emit);
      case 'navigate':
        _handleMapNavigation(event, currentState, emit);
      case 'add_to_trip':
        _handleAddToTrip(event, currentState, emit);
      case 'check_weather':
        _handleCheckWeather(event, currentState, emit);
      default:
        emit(currentState.copyWith(
          nodeActionResult: NodeActionResult(
            type: NodeActionType.showMessage,
            nodeId: event.associationId,
            message: '暂不支持该操作',
          ),
        ));
    }
  }

  Future<void> _handleConfirmAction(
    ExecuteNodeAction event,
    InsightGraphLoaded currentState,
    Emitter<InsightGraphState> emit,
  ) async {
    try {
      await _repository.confirmItem(event.associationId);

      final updatedItems = currentState.data.associatedItems
          .where((item) => item.id != event.associationId)
          .toList();
      final updatedData = currentState.data.copyWith(associatedItems: updatedItems);
      final filteredItems = _applyFilter(updatedItems, currentState.activeFilter);

      emit(currentState.copyWith(
        data: updatedData,
        filteredItems: filteredItems,
        nodeActionResult: NodeActionResult(
          type: NodeActionType.confirmed,
          nodeId: event.associationId,
          message: '已确认',
        ),
      ));
    } catch (e) {
      emit(currentState.copyWith(
        nodeActionResult: NodeActionResult(
          type: NodeActionType.error,
          nodeId: event.associationId,
          message: '确认失败: $e',
        ),
      ));
    }
  }

  Future<void> _handleDismissAction(
    ExecuteNodeAction event,
    InsightGraphLoaded currentState,
    Emitter<InsightGraphState> emit,
  ) async {
    try {
      final correction = event.targetData['correction'] as String?;
      await _repository.dismissItem(event.associationId, correction: correction);

      final updatedItems = currentState.data.associatedItems
          .where((item) => item.id != event.associationId)
          .toList();
      final updatedData = currentState.data.copyWith(associatedItems: updatedItems);
      final filteredItems = _applyFilter(updatedItems, currentState.activeFilter);

      emit(currentState.copyWith(
        data: updatedData,
        filteredItems: filteredItems,
        nodeActionResult: NodeActionResult(
          type: NodeActionType.dismissed,
          nodeId: event.associationId,
          message: '已忽略',
        ),
      ));
    } catch (e) {
      emit(currentState.copyWith(
        nodeActionResult: NodeActionResult(
          type: NodeActionType.error,
          nodeId: event.associationId,
          message: '忽略失败: $e',
        ),
      ));
    }
  }

  Future<void> _handleSnoozeAction(
    ExecuteNodeAction event,
    InsightGraphLoaded currentState,
    Emitter<InsightGraphState> emit,
  ) async {
    try {
      final minutes = event.targetData['snooze_minutes'] as int? ?? 60;
      await _repository.snoozeItem(event.associationId, Duration(minutes: minutes));

      final updatedItems = currentState.data.associatedItems
          .where((item) => item.id != event.associationId)
          .toList();
      final updatedData = currentState.data.copyWith(associatedItems: updatedItems);
      final filteredItems = _applyFilter(updatedItems, currentState.activeFilter);

      emit(currentState.copyWith(
        data: updatedData,
        filteredItems: filteredItems,
        nodeActionResult: NodeActionResult(
          type: NodeActionType.showMessage,
          nodeId: event.associationId,
          message: '已延后',
        ),
      ));
    } catch (e) {
      emit(currentState.copyWith(
        nodeActionResult: NodeActionResult(
          type: NodeActionType.error,
          nodeId: event.associationId,
          message: '延后失败: $e',
        ),
      ));
    }
  }

  void _handleNavigateToChat(
    ExecuteNodeAction event,
    InsightGraphLoaded currentState,
    Emitter<InsightGraphState> emit, {
    required String prefill,
  }) {
    final label = event.targetData['label'] as String? ?? '';
    emit(currentState.copyWith(
      nodeActionResult: NodeActionResult(
        type: NodeActionType.navigate,
        nodeId: event.associationId,
        routePath: '/conversation',
        routeExtra: {'prefill': '$prefill $label'.trim()},
        message: label,
      ),
    ));
  }

  void _handleViewDetail(
    ExecuteNodeAction event,
    InsightGraphLoaded currentState,
    Emitter<InsightGraphState> emit,
  ) {
    final nodeType = event.targetData['type'] as String? ?? '';
    final nodeData = event.targetData['data'] as Map<String, dynamic>? ?? {};
    String? routePath;

    switch (nodeType) {
      case 'person':
        final memberId = nodeData['member_id'] as String?;
        if (memberId != null) {
          routePath = '/members/$memberId';
        }
      case 'place':
        final tripId = nodeData['trip_id'] as String?;
        if (tripId != null) {
          routePath = '/trips/$tripId';
        }
      case 'event':
        final eventId = nodeData['event_id'] as String?;
        if (eventId != null) {
          routePath = '/trips/$eventId';
        }
      case 'task':
        routePath = '/conversation';
    }

    if (routePath != null) {
      emit(currentState.copyWith(
        nodeActionResult: NodeActionResult(
          type: NodeActionType.navigate,
          nodeId: event.associationId,
          routePath: routePath,
          message: '查看详情',
        ),
      ));
    } else {
      emit(currentState.copyWith(
        nodeActionResult: NodeActionResult(
          type: NodeActionType.showMessage,
          nodeId: event.associationId,
          message: '暂无详情页面',
        ),
      ));
    }
  }

  void _handleAddToTrip(
    ExecuteNodeAction event,
    InsightGraphLoaded currentState,
    Emitter<InsightGraphState> emit,
  ) {
    final nodeData = event.targetData['data'] as Map<String, dynamic>? ?? {};
    final tripId = nodeData['trip_id'] as String?;
    if (tripId != null) {
      emit(currentState.copyWith(
        nodeActionResult: NodeActionResult(
          type: NodeActionType.navigate,
          nodeId: event.associationId,
          routePath: '/trips/$tripId',
          message: '查看行程',
        ),
      ));
    } else {
      final label = event.targetData['label'] as String? ?? '';
      final location = nodeData['location'] as String?;
      final startTime = nodeData['start_time'] as String?;
      emit(currentState.copyWith(
        nodeActionResult: NodeActionResult(
          type: NodeActionType.navigate,
          nodeId: event.associationId,
          routePath: '/trips/create',
          routeExtra: {
            'prefill_title': label,
            if (location != null) 'prefill_location': location,
            if (startTime != null) 'prefill_start_time': startTime,
          },
          message: '创建行程',
        ),
      ));
    }
  }

  void _handleCheckWeather(
    ExecuteNodeAction event,
    InsightGraphLoaded currentState,
    Emitter<InsightGraphState> emit,
  ) {
    final label = event.targetData['label'] as String? ?? '';
    final nodeData = event.targetData['data'] as Map<String, dynamic>? ?? {};
    final location = nodeData['location'] as String? ?? label;
    emit(currentState.copyWith(
      nodeActionResult: NodeActionResult(
        type: NodeActionType.navigate,
        nodeId: event.associationId,
        routePath: '/conversation',
        routeExtra: {'prefill': '查看$location的天气'},
        message: '查天气',
      ),
    ));
  }

  void _handlePrepareGift(
    ExecuteNodeAction event,
    InsightGraphLoaded currentState,
    Emitter<InsightGraphState> emit,
  ) {
    final memberId = (event.targetData['data'] as Map<String, dynamic>?)?['member_id'] as String?;
    if (memberId != null) {
      emit(currentState.copyWith(
        nodeActionResult: NodeActionResult(
          type: NodeActionType.navigate,
          nodeId: event.associationId,
          routePath: '/discover/recommend/$memberId',
          message: '推荐礼物',
        ),
      ));
    } else {
      _handleNavigateToChat(event, currentState, emit, prefill: '帮我准备一份礼物');
    }
  }

  void _handleMapNavigation(
    ExecuteNodeAction event,
    InsightGraphLoaded currentState,
    Emitter<InsightGraphState> emit,
  ) {
    final label = event.targetData['label'] as String? ?? '';
    final data = event.targetData['data'] as Map<String, dynamic>? ?? {};
    final lat = data['latitude'];
    final lng = data['longitude'];
    String? mapUrl;
    if (lat != null && lng != null) {
      mapUrl = 'https://maps.apple.com/?q=$label&ll=$lat,$lng';
    } else if (label.isNotEmpty) {
      mapUrl = 'https://maps.apple.com/?q=${Uri.encodeComponent(label)}';
    }

    emit(currentState.copyWith(
      nodeActionResult: NodeActionResult(
        type: NodeActionType.navigate,
        nodeId: event.associationId,
        routePath: mapUrl,
        routeExtra: {'external': true},
        message: '导航到 $label',
      ),
    ));
  }

  /// PRD 2.3.2: 加载行程的图谱数据并更新核心事件和关联
  Future<void> _onLoadTripGraph(
    LoadTripGraph event,
    Emitter<InsightGraphState> emit,
  ) async {
    final currentState = state;

    if (currentState is InsightGraphLoaded) {
      try {
        // Load both insight graph and event graph in parallel
        final results = await Future.wait([
          _repository.getInsightGraphForEvent(event.tripId),
          _repository.getEventGraph(event.tripId).then<EventGraphResponse?>((v) => v).catchError((_) => null),
        ]);

        final data = results[0] as InsightGraphData?;
        final eventGraph = results[1] as EventGraphResponse?;

        if (data != null) {
          // Preserve upcoming trips and selected trip, update core data
          final filteredItems = _applyFilter(
            data.associatedItems,
            currentState.activeFilter,
          );

          emit(InsightGraphLoaded(
            data: data,
            activeFilter: currentState.activeFilter,
            filteredItems: filteredItems,
            upcomingTrips: currentState.upcomingTrips,
            selectedTripId: event.tripId,
            tripGraph: eventGraph,
          ));
        } else {
          // Build synthetic core event from TripSummary
          final tripSummary = currentState.upcomingTrips
              .where((t) => t.id == event.tripId)
              .firstOrNull;
          if (tripSummary != null) {
            final syntheticEvent = CoreEventModel(
              id: tripSummary.id,
              title: tripSummary.title,
              subtitle: '行程尚未整理，稍后将自动更新',
              location: tripSummary.location,
              startDate: tripSummary.startDate,
              endDate: tripSummary.endDate,
              eventType: EventType.travel,
              metadata: {
                'trip_id': tripSummary.id,
                'trip_name': tripSummary.title,
              },
            );
            emit(InsightGraphLoaded(
              data: InsightGraphData.empty(syntheticEvent),
              filteredItems: const [],
              upcomingTrips: currentState.upcomingTrips,
              selectedTripId: event.tripId,
              tripGraph: eventGraph,
            ));
          } else {
            emit(currentState.copyWith(isRefreshing: false));
          }
        }
      } catch (e) {
        // On error, stop refreshing indicator
        emit(currentState.copyWith(isRefreshing: false));
      }
    }
  }
}
