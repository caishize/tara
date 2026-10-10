import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/datasources/insight_graph_remote_datasource.dart';
import '../bloc/insight_graph_bloc.dart';
import '../bloc/insight_graph_event.dart';
import '../bloc/insight_graph_state.dart';

/// Displays an event graph as a radial "hub-and-spoke" visualization.
///
/// The trip/core event sits at the center. Related nodes (person, event,
/// time, place, task) are arranged in a circle around it, grouped by type.
/// Edges are drawn as curved lines between connected nodes.
class EventGraphView extends StatefulWidget {
  final EventGraphResponse graph;
  final void Function(GraphNode node)? onNodeTap;

  const EventGraphView({
    super.key,
    required this.graph,
    this.onNodeTap,
  });

  @override
  State<EventGraphView> createState() => _EventGraphViewState();
}

class _EventGraphViewState extends State<EventGraphView>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _scaleAnim;
  String? _selectedNodeId;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _scaleAnim = CurvedAnimation(
      parent: _animController,
      curve: Curves.easeOutBack,
    );
    _animController.forward();
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.graph.nodes.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Center(
          child: Text(
            '暂无关联数据',
            style: TextStyle(fontSize: 14, color: AppColors.textTertiary),
          ),
        ),
      );
    }

    return BlocListener<InsightGraphBloc, InsightGraphState>(
      listenWhen: (prev, curr) {
        if (prev is InsightGraphLoaded && curr is InsightGraphLoaded) {
          return prev.nodeActionResult != curr.nodeActionResult;
        }
        return false;
      },
      listener: (context, state) {
        if (state is! InsightGraphLoaded) return;
        final result = state.nodeActionResult;
        if (result == null) return;

        switch (result.type) {
          case NodeActionType.confirmed:
          case NodeActionType.dismissed:
          case NodeActionType.showMessage:
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(result.message ?? '操作完成'),
                duration: const Duration(seconds: 2),
              ),
            );
            if (result.type == NodeActionType.dismissed) {
              setState(() {
                if (_selectedNodeId == result.nodeId) {
                  _selectedNodeId = null;
                }
              });
            }
          case NodeActionType.navigate:
            final path = result.routePath;
            if (path == null) break;
            final isExternal = result.routeExtra?['external'] == true;
            if (isExternal) {
              final uri = Uri.tryParse(path);
              if (uri != null) {
                launchUrl(uri, mode: LaunchMode.externalApplication);
              }
            } else {
              context.push(path, extra: result.routeExtra);
            }
          case NodeActionType.error:
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(result.message ?? '操作失败'),
                backgroundColor: Colors.red.shade700,
                duration: const Duration(seconds: 3),
              ),
            );
        }
      },
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                const Icon(Icons.hub, size: 18, color: AppColors.primary),
                const SizedBox(width: 8),
                const Text(
                  '关联图谱',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                const Spacer(),
                Text(
                  '${widget.graph.nodes.length} 节点 / ${widget.graph.edges.length} 关联',
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          ),

          // Radial graph
          SizedBox(
            height: 320,
            child: AnimatedBuilder(
              animation: _scaleAnim,
              builder: (context, _) => LayoutBuilder(
                builder: (context, constraints) {
                  return _RadialGraph(
                    graph: widget.graph,
                    width: constraints.maxWidth,
                    height: 320,
                    animValue: _scaleAnim.value,
                    selectedNodeId: _selectedNodeId,
                    onNodeTap: (node) {
                      setState(() {
                        _selectedNodeId =
                            _selectedNodeId == node.id ? null : node.id;
                      });
                      widget.onNodeTap?.call(node);
                    },
                  );
                },
              ),
            ),
          ),

          // Legend
          _buildLegend(),

          // Selected node detail
          if (_selectedNodeId != null) _buildSelectedDetail(),
        ],
      ),
    );
  }

  Widget _buildLegend() {
    final types = <String>{};
    for (final n in widget.graph.nodes) {
      types.add(n.type);
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Wrap(
        spacing: 12,
        runSpacing: 4,
        children: types.map((type) {
          return Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  color: _typeColor(type),
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                _typeLabel(type),
                style: const TextStyle(
                  fontSize: 11,
                  color: AppColors.textTertiary,
                ),
              ),
            ],
          );
        }).toList(),
      ),
    );
  }

  Widget _buildSelectedDetail() {
    final node = widget.graph.nodes.firstWhere(
      (n) => n.id == _selectedNodeId,
      orElse: () => widget.graph.nodes.first,
    );

    final connections = widget.graph.edges
        .where((e) => e.source == node.id || e.target == node.id)
        .toList();

    final nodeMap = {for (final n in widget.graph.nodes) n.id: n};

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: _typeColor(node.type).withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                _typeIcon(node.type),
                size: 16,
                color: _typeColor(node.type),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  node.label,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
              ),
              if (node.status != null)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    node.status!,
                    style: const TextStyle(
                      fontSize: 10,
                      color: AppColors.primary,
                    ),
                  ),
                ),
            ],
          ),
          if (connections.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 4,
              children: connections.map((edge) {
                final otherId =
                    edge.source == node.id ? edge.target : edge.source;
                final other = nodeMap[otherId];
                if (other == null) return const SizedBox.shrink();
                return Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: _typeColor(other.type).withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(
                      color: _typeColor(other.type).withValues(alpha: 0.2),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        _typeIcon(other.type),
                        size: 10,
                        color: _typeColor(other.type),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        other.label,
                        style: TextStyle(
                          fontSize: 11,
                          color: _typeColor(other.type),
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ],

          // Action buttons
          if (node.availableActions.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Divider(height: 1),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: node.availableActions.map((action) {
                return _ActionButton(
                  action: action,
                  onTap: () {
                    context.read<InsightGraphBloc>().add(
                      ExecuteNodeAction(
                        actionType: action,
                        associationId: node.id,
                        targetData: {
                          'label': node.label,
                          'type': node.type,
                          'data': node.data ?? {},
                        },
                      ),
                    );
                  },
                );
              }).toList(),
            ),
          ],
        ],
      ),
    );
  }
}

// ----- Radial graph widget using CustomPainter -----

class _RadialGraph extends StatelessWidget {
  final EventGraphResponse graph;
  final double width;
  final double height;
  final double animValue;
  final String? selectedNodeId;
  final void Function(GraphNode) onNodeTap;

  const _RadialGraph({
    required this.graph,
    required this.width,
    required this.height,
    required this.animValue,
    required this.selectedNodeId,
    required this.onNodeTap,
  });

  @override
  Widget build(BuildContext context) {
    final center = Offset(width / 2, height / 2);
    final radius = math.min(width, height) / 2 - 40;
    final nodePositions = _layoutNodes(center, radius);
    final nodeMap = {for (final n in graph.nodes) n.id: n};

    return Stack(
      children: [
        // Edge lines (painted below nodes)
        CustomPaint(
          size: Size(width, height),
          painter: _EdgePainter(
            edges: graph.edges,
            positions: nodePositions,
            selectedNodeId: selectedNodeId,
            animValue: animValue,
          ),
        ),

        // Center hub label (trip name) — core node: up to 8 grapheme clusters
        Positioned(
          left: center.dx - 40,
          top: center.dy - 14,
          child: SizedBox(
            width: 80,
            child: Text(
              _truncateCoreLabel(graph.trip.location ?? graph.trip.title, 8),
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
          ),
        ),

        // Center hub dot
        Positioned(
          left: center.dx - 18,
          top: center.dy - 32,
          child: Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppColors.primary,
              boxShadow: [
                BoxShadow(
                  color: AppColors.primary.withValues(alpha: 0.3),
                  blurRadius: 8,
                  spreadRadius: 2,
                ),
              ],
            ),
            child: const Icon(Icons.hub, size: 18, color: Colors.white),
          ),
        ),

        // Surrounding nodes
        ...nodePositions.entries.map((entry) {
          final nodeId = entry.key;
          final pos = entry.value;
          final node = nodeMap[nodeId];
          if (node == null) return const SizedBox.shrink();

          final isSelected = selectedNodeId == nodeId;
          final animPos = Offset(
            center.dx + (pos.dx - center.dx) * animValue,
            center.dy + (pos.dy - center.dy) * animValue,
          );

          return Positioned(
            left: animPos.dx - 22,
            top: animPos.dy - 22,
            child: GestureDetector(
              onTap: () => onNodeTap(node),
              child: _RadialNode(
                node: node,
                isSelected: isSelected,
              ),
            ),
          );
        }),
      ],
    );
  }

  /// Truncate core node label using grapheme clusters (correct for CJK).
  static String _truncateCoreLabel(String text, int maxLen) {
    final chars = text.characters;
    if (chars.length <= maxLen) return text;
    return '${chars.take(maxLen)}..';
  }

  /// Arrange nodes in a circle around center, grouped by type.
  Map<String, Offset> _layoutNodes(Offset center, double radius) {
    final grouped = <String, List<GraphNode>>{};
    for (final n in graph.nodes) {
      grouped.putIfAbsent(n.type, () => []).add(n);
    }

    final typeOrder = ['person', 'event', 'time', 'place', 'task'];
    final sortedTypes = grouped.keys.toList()
      ..sort((a, b) {
        final ia = typeOrder.indexOf(a);
        final ib = typeOrder.indexOf(b);
        return (ia == -1 ? 99 : ia).compareTo(ib == -1 ? 99 : ib);
      });

    final totalNodes = graph.nodes.length;
    if (totalNodes == 0) return {};

    final positions = <String, Offset>{};
    var idx = 0;

    for (final type in sortedTypes) {
      final nodes = grouped[type]!;
      for (final node in nodes) {
        final angle = (2 * math.pi * idx / totalNodes) - math.pi / 2;
        positions[node.id] = Offset(
          center.dx + radius * math.cos(angle),
          center.dy + radius * math.sin(angle),
        );
        idx++;
      }
    }

    return positions;
  }
}

class _RadialNode extends StatelessWidget {
  final GraphNode node;
  final bool isSelected;

  const _RadialNode({
    required this.node,
    required this.isSelected,
  });

  @override
  Widget build(BuildContext context) {
    final color = _typeColor(node.type);
    // Regular surrounding nodes: 6 grapheme clusters max
    const maxChars = 6;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: isSelected ? color : color.withValues(alpha: 0.15),
        border: Border.all(
          color: isSelected ? color : color.withValues(alpha: 0.4),
          width: isSelected ? 2.5 : 1.5,
        ),
        boxShadow: isSelected
            ? [
                BoxShadow(
                  color: color.withValues(alpha: 0.3),
                  blurRadius: 8,
                  spreadRadius: 1,
                )
              ]
            : null,
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            _typeIcon(node.type),
            size: 14,
            color: isSelected ? Colors.white : color,
          ),
          Text(
            _truncateGrapheme(node.label, maxChars),
            style: TextStyle(
              fontSize: 8,
              fontWeight: FontWeight.w600,
              color: isSelected ? Colors.white : color,
            ),
            maxLines: 1,
            overflow: TextOverflow.clip,
          ),
        ],
      ),
    );
  }

  /// Truncate using grapheme clusters (correct for CJK characters).
  static String _truncateGrapheme(String text, int maxLen) {
    final chars = text.characters;
    if (chars.length <= maxLen) return text;
    return '${chars.take(maxLen)}..';
  }
}

class _EdgePainter extends CustomPainter {
  final List<GraphEdge> edges;
  final Map<String, Offset> positions;
  final String? selectedNodeId;
  final double animValue;

  _EdgePainter({
    required this.edges,
    required this.positions,
    required this.selectedNodeId,
    required this.animValue,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2 - 14);

    for (final entry in positions.entries) {
      final pos = entry.value;
      final animPos = Offset(
        center.dx + (pos.dx - center.dx) * animValue,
        center.dy + (pos.dy - center.dy) * animValue,
      );

      final isHighlighted = selectedNodeId == entry.key;
      final paint = Paint()
        ..color = isHighlighted
            ? AppColors.primary.withValues(alpha: 0.5)
            : AppColors.primary.withValues(alpha: 0.12)
        ..strokeWidth = isHighlighted ? 1.5 : 0.8
        ..style = PaintingStyle.stroke;

      canvas.drawLine(center, animPos, paint);
    }

    for (final edge in edges) {
      final from = positions[edge.source];
      final to = positions[edge.target];
      if (from == null || to == null) continue;

      final animFrom = Offset(
        center.dx + (from.dx - center.dx) * animValue,
        center.dy + (from.dy - center.dy) * animValue,
      );
      final animTo = Offset(
        center.dx + (to.dx - center.dx) * animValue,
        center.dy + (to.dy - center.dy) * animValue,
      );

      final isHighlighted =
          selectedNodeId == edge.source || selectedNodeId == edge.target;

      final paint = Paint()
        ..color = isHighlighted
            ? const Color(0xFFF59E0B).withValues(alpha: 0.6)
            : const Color(0xFFF59E0B).withValues(alpha: 0.15)
        ..strokeWidth = isHighlighted ? 2.0 : 1.0
        ..style = PaintingStyle.stroke;

      final mid = Offset(
        (animFrom.dx + animTo.dx) / 2 +
            (animTo.dy - animFrom.dy) * 0.15,
        (animFrom.dy + animTo.dy) / 2 -
            (animTo.dx - animFrom.dx) * 0.15,
      );

      final path = Path()
        ..moveTo(animFrom.dx, animFrom.dy)
        ..quadraticBezierTo(mid.dx, mid.dy, animTo.dx, animTo.dy);

      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _EdgePainter old) {
    return old.animValue != animValue || old.selectedNodeId != selectedNodeId;
  }
}

// ----- Shared helpers -----

String _typeLabel(String type) {
  switch (type) {
    case 'person':
      return '人物';
    case 'event':
      return '事件';
    case 'time':
      return '时间';
    case 'place':
      return '地点';
    case 'task':
      return '待办';
    default:
      return type;
  }
}

IconData _typeIcon(String type) {
  switch (type) {
    case 'person':
      return Icons.person_outline;
    case 'event':
      return Icons.event_note;
    case 'time':
      return Icons.schedule;
    case 'place':
      return Icons.place_outlined;
    case 'task':
      return Icons.check_circle_outline;
    default:
      return Icons.circle_outlined;
  }
}

Color _typeColor(String type) {
  switch (type) {
    case 'person':
      return const Color(0xFF8B5CF6);
    case 'event':
      return const Color(0xFF3B82F6);
    case 'time':
      return const Color(0xFFF59E0B);
    case 'place':
      return AppColors.primary;
    case 'task':
      return const Color(0xFF10B981);
    default:
      return AppColors.textSecondary;
  }
}

// ----- Action button -----

class _ActionButton extends StatelessWidget {
  final String action;
  final VoidCallback onTap;

  const _ActionButton({required this.action, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final config = _actionConfig(action);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: config.color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: config.color.withValues(alpha: 0.25)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(config.icon, size: 14, color: config.color),
              const SizedBox(width: 4),
              Text(
                config.label,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: config.color,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static _ActionConfig _actionConfig(String action) {
    switch (action) {
      case 'confirm':
        return _ActionConfig('确认', Icons.check_circle_outline, const Color(0xFF10B981));
      case 'dismiss':
        return _ActionConfig('忽略', Icons.cancel_outlined, AppColors.textTertiary);
      case 'send_greeting':
        return _ActionConfig('发送问候', Icons.chat_bubble_outline, const Color(0xFF8B5CF6));
      case 'view_profile':
        return _ActionConfig('查看资料', Icons.person_outline, const Color(0xFF8B5CF6));
      case 'send_gift':
        return _ActionConfig('送礼', Icons.card_giftcard, const Color(0xFFEF4444));
      case 'mark_done':
        return _ActionConfig('完成', Icons.done_all, const Color(0xFF10B981));
      case 'set_reminder':
        return _ActionConfig('提醒', Icons.alarm_add, const Color(0xFFF59E0B));
      case 'snooze':
        return _ActionConfig('稍后', Icons.snooze, const Color(0xFFF59E0B));
      case 'navigate':
        return _ActionConfig('导航', Icons.navigation_outlined, AppColors.primary);
      case 'view_details':
        return _ActionConfig('详情', Icons.info_outline, const Color(0xFF3B82F6));
      case 'add_to_trip':
        return _ActionConfig('加入行程', Icons.add_location_alt_outlined, const Color(0xFF06B6D4));
      case 'check_weather':
        return _ActionConfig('查天气', Icons.wb_sunny_outlined, const Color(0xFFF59E0B));
      default:
        return _ActionConfig(action, Icons.touch_app, AppColors.textSecondary);
    }
  }
}

class _ActionConfig {
  final String label;
  final IconData icon;
  final Color color;

  const _ActionConfig(this.label, this.icon, this.color);
}
