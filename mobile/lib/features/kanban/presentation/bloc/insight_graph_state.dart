import 'package:equatable/equatable.dart';

import '../../data/datasources/insight_graph_remote_datasource.dart';
import '../../domain/entities/associated_item.dart';
import '../../domain/entities/insight_graph_data.dart';

/// 动态图谱状态基类
abstract class InsightGraphState extends Equatable {
  const InsightGraphState();

  @override
  List<Object?> get props => [];
}

/// 初始状态
class InsightGraphInitial extends InsightGraphState {
  const InsightGraphInitial();
}

/// 加载中状态
class InsightGraphLoading extends InsightGraphState {
  const InsightGraphLoading();
}

/// 加载成功状态
class InsightGraphLoaded extends InsightGraphState {
  final InsightGraphData data;
  final ItemType? activeFilter;
  final List<AssociatedItem> filteredItems;
  final bool isRefreshing;

  /// PRD 2.3.2: 即将到来的行程列表（用于切换）
  final List<TripSummary> upcomingTrips;
  /// PRD 2.3.2: 当前选中的行程ID
  final String? selectedTripId;
  /// PRD 2.3.2: 当前行程的事件图谱
  final EventGraphResponse? tripGraph;
  /// Transient error message from a failed operation (dismiss/confirm/snooze).
  /// UI should show as SnackBar then clear on next state change.
  final String? operationError;

  /// Result of an ExecuteNodeAction — used by UI to show SnackBar, navigate, etc.
  final NodeActionResult? nodeActionResult;

  const InsightGraphLoaded({
    required this.data,
    this.activeFilter,
    required this.filteredItems,
    this.isRefreshing = false,
    this.upcomingTrips = const [],
    this.selectedTripId,
    this.tripGraph,
    this.operationError,
    this.nodeActionResult,
  });

  /// 获取筛选后的事项数量
  int get filteredCount => filteredItems.length;

  /// 是否有筛选条件
  bool get hasFilter => activeFilter != null;

  /// PRD 2.3.2: 是否有多个行程可切换
  bool get hasMultipleTrips => upcomingTrips.length > 1;

  /// 创建副本
  InsightGraphLoaded copyWith({
    InsightGraphData? data,
    ItemType? activeFilter,
    List<AssociatedItem>? filteredItems,
    bool? isRefreshing,
    bool clearFilter = false,
    List<TripSummary>? upcomingTrips,
    String? selectedTripId,
    EventGraphResponse? tripGraph,
    bool clearTripGraph = false,
    String? operationError,
    bool clearOperationError = false,
    NodeActionResult? nodeActionResult,
    bool clearNodeActionResult = false,
  }) {
    return InsightGraphLoaded(
      data: data ?? this.data,
      activeFilter: clearFilter ? null : (activeFilter ?? this.activeFilter),
      filteredItems: filteredItems ?? this.filteredItems,
      isRefreshing: isRefreshing ?? this.isRefreshing,
      upcomingTrips: upcomingTrips ?? this.upcomingTrips,
      selectedTripId: selectedTripId ?? this.selectedTripId,
      tripGraph: clearTripGraph ? null : (tripGraph ?? this.tripGraph),
      operationError: clearOperationError ? null : operationError,
      nodeActionResult: clearNodeActionResult ? null : nodeActionResult,
    );
  }

  @override
  List<Object?> get props => [data, activeFilter, filteredItems, isRefreshing, upcomingTrips, selectedTripId, tripGraph, operationError, nodeActionResult];
}

/// 空数据状态
class InsightGraphEmpty extends InsightGraphState {
  final String message;

  const InsightGraphEmpty({
    this.message = '暂无关联事项',
  });

  @override
  List<Object?> get props => [message];
}

/// 错误状态
class InsightGraphError extends InsightGraphState {
  final String message;
  final InsightGraphErrorType errorType;

  const InsightGraphError({
    required this.message,
    this.errorType = InsightGraphErrorType.unknown,
  });

  @override
  List<Object?> get props => [message, errorType];
}

/// 错误类型枚举
enum InsightGraphErrorType {
  network,
  server,
  notFound,
  unknown,
}

/// Node action result types
enum NodeActionType {
  /// API-based: confirm/dismiss succeeded
  confirmed,
  dismissed,
  /// Navigation: UI should navigate to a route
  navigate,
  /// Show a message via SnackBar
  showMessage,
  /// Error during action execution
  error,
}

/// Result of an ExecuteNodeAction, consumed by UI layer
class NodeActionResult extends Equatable {
  final NodeActionType type;
  final String nodeId;
  /// For navigation actions: the route path to push
  final String? routePath;
  /// For navigation actions: extra data to pass
  final Map<String, dynamic>? routeExtra;
  /// Human-readable message for SnackBar
  final String? message;
  /// Unique timestamp to force state change even for same action type
  final int timestamp;

  NodeActionResult({
    required this.type,
    required this.nodeId,
    this.routePath,
    this.routeExtra,
    this.message,
  }) : timestamp = DateTime.now().microsecondsSinceEpoch;

  @override
  List<Object?> get props => [type, nodeId, routePath, message, timestamp];
}
