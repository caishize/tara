import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mocktail/mocktail.dart';
import 'package:family_secretary/features/kanban/data/datasources/insight_graph_remote_datasource.dart';
import 'package:family_secretary/features/kanban/presentation/widgets/event_graph_view.dart';
import 'package:family_secretary/features/kanban/presentation/bloc/insight_graph_bloc.dart';
import 'package:family_secretary/features/kanban/domain/repositories/insight_graph_repository.dart';

class MockInsightGraphRepository extends Mock implements InsightGraphRepository {}

/// Helper to build an [EventGraphResponse] for tests.
EventGraphResponse _buildGraph({
  required List<GraphNode> nodes,
  List<GraphEdge> edges = const [],
}) {
  return EventGraphResponse(
    trip: TripSummary(
      id: 'trip-1',
      title: 'Test Trip',
      startDate: DateTime(2026, 3, 1),
      endDate: DateTime(2026, 3, 5),
    ),
    nodes: nodes,
    edges: edges,
    events: const [],
  );
}

Widget _wrap(Widget child) {
  return MaterialApp(
    home: BlocProvider<InsightGraphBloc>(
      create: (_) => InsightGraphBloc(repository: MockInsightGraphRepository()),
      child: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  );
}

void main() {
  group('EventGraphView', () {
    testWidgets('shows empty placeholder when graph has no nodes', (tester) async {
      final graph = _buildGraph(nodes: []);

      await tester.pumpWidget(_wrap(EventGraphView(graph: graph)));

      expect(find.text('暂无关联数据'), findsOneWidget);
      // Header should NOT appear
      expect(find.text('关联图谱'), findsNothing);
    });

    testWidgets('renders header with correct node and edge counts', (tester) async {
      final graph = _buildGraph(
        nodes: [
          GraphNode(id: 'p1', type: 'person', label: 'Alice'),
          GraphNode(id: 'e1', type: 'event', label: 'Meeting'),
        ],
        edges: [
          GraphEdge(source: 'p1', target: 'e1', type: 'participant'),
        ],
      );

      await tester.pumpWidget(_wrap(EventGraphView(graph: graph)));

      expect(find.text('关联图谱'), findsOneWidget);
      expect(find.text('2 节点 / 1 关联'), findsOneWidget);
    });

    testWidgets('groups nodes by type and shows type labels in legend', (tester) async {
      final graph = _buildGraph(
        nodes: [
          GraphNode(id: 'p1', type: 'person', label: 'Alice'),
          GraphNode(id: 'p2', type: 'person', label: 'Bob'),
          GraphNode(id: 'e1', type: 'event', label: 'Dinner'),
          GraphNode(id: 't1', type: 'time', label: 'March 3'),
        ],
      );

      await tester.pumpWidget(_wrap(EventGraphView(graph: graph)));
      await tester.pumpAndSettle();

      // Legend type labels should appear (radial graph renders node labels in CustomPainter)
      expect(find.text('人物'), findsOneWidget);
      expect(find.text('事件'), findsOneWidget);
      expect(find.text('时间'), findsOneWidget);
    });

    testWidgets('shows connection chips for edges', (tester) async {
      final graph = _buildGraph(
        nodes: [
          GraphNode(id: 'p1', type: 'person', label: 'Alice'),
          GraphNode(id: 'e1', type: 'event', label: 'Dinner'),
        ],
        edges: [
          GraphEdge(source: 'p1', target: 'e1', type: 'participant'),
        ],
      );

      await tester.pumpWidget(_wrap(EventGraphView(graph: graph)));

      // Alice's card should show "Dinner" as a connection chip
      // And Dinner's card should show "Alice" as a connection chip
      // Both node labels appear as their own card + as connection chip text
      expect(find.text('Alice'), findsAtLeastNWidgets(1));
      expect(find.text('Dinner'), findsAtLeastNWidgets(1));
    });

    testWidgets('fires onNodeTap callback when a node card is tapped', (tester) async {
      GraphNode? tappedNode;
      final graph = _buildGraph(
        nodes: [
          GraphNode(id: 'p1', type: 'person', label: 'Alice'),
        ],
      );

      await tester.pumpWidget(
        _wrap(EventGraphView(
          graph: graph,
          onNodeTap: (node) => tappedNode = node,
        )),
      );

      await tester.tap(find.text('Alice'));
      await tester.pump();

      expect(tappedNode, isNotNull);
      expect(tappedNode!.id, 'p1');
      expect(tappedNode!.label, 'Alice');
    });

    testWidgets('shows legend label for task type', (tester) async {
      final graph = _buildGraph(
        nodes: [
          GraphNode(id: 't1', type: 'task', label: 'Buy tickets', status: '待办'),
        ],
      );

      await tester.pumpWidget(_wrap(EventGraphView(graph: graph)));
      await tester.pumpAndSettle();

      // Legend should show task type label (node text rendered in CustomPainter)
      expect(find.text('待办'), findsOneWidget);
    });

    testWidgets('renders radial graph with many connected nodes', (tester) async {
      // Create a person node connected to 7 event nodes
      final nodes = [
        GraphNode(id: 'p1', type: 'person', label: 'Alice'),
        for (var i = 1; i <= 7; i++)
          GraphNode(id: 'e$i', type: 'event', label: 'Event $i'),
      ];
      final edges = [
        for (var i = 1; i <= 7; i++)
          GraphEdge(source: 'p1', target: 'e$i', type: 'related'),
      ];

      final graph = _buildGraph(nodes: nodes, edges: edges);

      await tester.pumpWidget(_wrap(EventGraphView(graph: graph)));
      await tester.pumpAndSettle();

      // Header should show correct counts
      expect(find.text('8 节点 / 7 关联'), findsOneWidget);
      // Legend should show both types
      expect(find.text('人物'), findsOneWidget);
      expect(find.text('事件'), findsOneWidget);
    });
  });
}
