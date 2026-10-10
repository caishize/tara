/// Insight Graph feature module - Event-centric intelligent association
///
/// This module provides a dynamic graph view that takes a core event
/// (e.g., business trip, travel, meeting) and surfaces related people,
/// tasks, gifts, and potential conflicts.
library insight_graph;

// Domain
export 'domain/entities/core_event.dart';
export 'domain/entities/associated_item.dart';
export 'domain/entities/conflict_alert.dart';
export 'domain/entities/insight_graph_data.dart';
export 'domain/repositories/insight_graph_repository.dart';

// Data
export 'data/models/core_event_model.dart';
export 'data/models/associated_item_model.dart';
export 'data/models/conflict_alert_model.dart';
export 'data/datasources/insight_graph_remote_datasource.dart';
export 'data/repositories/insight_graph_repository_impl.dart';

// Presentation - BLoC
export 'presentation/bloc/insight_graph_bloc.dart';
export 'presentation/bloc/insight_graph_event.dart';
export 'presentation/bloc/insight_graph_state.dart';

// Presentation - Pages
export 'presentation/pages/insight_graph_page.dart';

// Presentation - Widgets
export 'presentation/widgets/core_event_card.dart';
export 'presentation/widgets/associated_item_card.dart';
export 'presentation/widgets/conflict_alert_card.dart';
export 'presentation/widgets/priority_badge.dart';
export 'presentation/widgets/context_hint_chip.dart';
export 'presentation/widgets/filter_chips.dart';
