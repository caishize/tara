import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../../../shared/utils/relation_utils.dart';
import '../bloc/relationships_bloc.dart';

/// Relationship graph visualization page with draggable nodes and member details
class RelationshipGraphPage extends StatelessWidget {
  const RelationshipGraphPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => getIt<RelationshipsBloc>()
        ..add(const RelationshipsGraphRequested()),
      child: const _RelationshipGraphContent(),
    );
  }
}

class _RelationshipGraphContent extends StatefulWidget {
  const _RelationshipGraphContent();

  @override
  State<_RelationshipGraphContent> createState() =>
      _RelationshipGraphContentState();
}

class _RelationshipGraphContentState extends State<_RelationshipGraphContent>
    with TickerProviderStateMixin {
  Map<String, dynamic>? _selectedNode;
  Offset _panOffset = Offset.zero;
  double _scale = 1.0;
  double _baseScale = 1.0; // Captured at gesture start

  // Store individual node positions (draggable)
  final Map<String, Offset> _nodePositions = {};
  String? _draggingNodeId;
  bool _isInitialized = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.cardBackground,
        elevation: 0,
        title: Text(
          '关系图谱',
          style: AppTextStyles.headline6.copyWith(color: AppColors.textPrimary),
        ),
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
        actions: [
          IconButton(
            onPressed: _resetView,
            icon: const Icon(Icons.center_focus_strong),
            tooltip: '重置视图',
            color: AppColors.textSecondary,
          ),
          IconButton(
            onPressed: _autoLayout,
            icon: const Icon(Icons.auto_fix_high),
            tooltip: '自动布局',
            color: AppColors.textSecondary,
          ),
        ],
      ),
      body: BlocBuilder<RelationshipsBloc, RelationshipsState>(
        builder: (context, state) {
          if (state is RelationshipsLoading) {
            return const Center(
              child: CircularProgressIndicator(color: AppColors.primary),
            );
          }

          if (state is RelationshipsError) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.error_outline, size: 48, color: AppColors.error.withValues(alpha: 0.5)),
                  const SizedBox(height: 16),
                  Text(state.message, style: AppTextStyles.bodyText1),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: () => context
                        .read<RelationshipsBloc>()
                        .add(const RelationshipsGraphRequested()),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                    ),
                    child: const Text('重试'),
                  ),
                ],
              ),
            );
          }

          if (state is RelationshipsGraphLoaded) {
            return _buildGraph(state.graphData);
          }

          return Center(
            child: Text(
              '加载关系图谱中...',
              style: AppTextStyles.bodyText2,
            ),
          );
        },
      ),
    );
  }

  Widget _buildGraph(Map<String, dynamic> graphData) {
    final nodes = (graphData['nodes'] as List?) ?? [];
    final edges = (graphData['edges'] as List?) ?? [];

    if (nodes.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.hub, size: 64, color: AppColors.textTertiary),
            const SizedBox(height: 16),
            Text(
              '暂无关系数据',
              style: AppTextStyles.subtitle1.copyWith(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 8),
            Text(
              '添加家庭成员后可查看关系图谱',
              style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
            ),
          ],
        ),
      );
    }

    // Initialize positions if not done yet
    if (!_isInitialized) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _initializeNodePositions(nodes);
      });
    }

    return Stack(
      children: [
        // Canvas for edges and nodes
        GestureDetector(
          onScaleStart: _draggingNodeId == null
              ? (details) {
                  _baseScale = _scale;
                }
              : null,
          onScaleUpdate: _draggingNodeId == null
              ? (details) {
                  final newScale = (_baseScale * details.scale).clamp(0.5, 2.5);
                  final delta = details.focalPointDelta;
                  if (newScale.isFinite && delta.dx.isFinite && delta.dy.isFinite) {
                    setState(() {
                      _scale = newScale;
                      _panOffset += delta;
                    });
                  }
                }
              : null,
          onTap: () {
            if (_selectedNode != null) {
              setState(() {
                _selectedNode = null;
              });
            }
          },
          child: CustomPaint(
            painter: _GraphPainter(
              nodes: nodes,
              edges: edges,
              nodePositions: _nodePositions,
              selectedNodeId: _selectedNode?['id'] as String?,
              panOffset: _panOffset,
              scale: _scale,
            ),
            child: SizedBox.expand(),
          ),
        ),
        // Interactive node overlays
        ..._buildNodeOverlays(nodes),
        // Hint text
        Positioned(
          left: 16,
          bottom: _selectedNode != null ? 200 : 16,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.cardBackground.withValues(alpha: 0.9),
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.05),
                  blurRadius: 4,
                ),
              ],
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.touch_app, size: 14, color: AppColors.textTertiary),
                const SizedBox(width: 6),
                Text(
                  '长按拖动节点 · 点击查看详情',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          ),
        ),
        // Member detail panel
        if (_selectedNode != null) _buildDetailPanel(),
      ],
    );
  }

  List<Widget> _buildNodeOverlays(List nodes) {
    return nodes.map((node) {
      final nodeId = node['id'] as String;
      final position = _nodePositions[nodeId];
      if (position == null) return const SizedBox.shrink();

      final adjustedPosition = Offset(
        position.dx * _scale + _panOffset.dx,
        position.dy * _scale + _panOffset.dy,
      );

      if (!adjustedPosition.dx.isFinite || !adjustedPosition.dy.isFinite) {
        return const SizedBox.shrink();
      }

      final importance = node['importance'] as int? ?? 3;
      final radius = (18.0 + importance * 3) * _scale;

      return Positioned(
        left: adjustedPosition.dx - radius,
        top: adjustedPosition.dy - radius,
        child: GestureDetector(
          onTap: () {
            HapticFeedback.lightImpact();
            setState(() {
              _selectedNode = _selectedNode?['id'] == nodeId ? null : node;
            });
          },
          onLongPressStart: (details) {
            HapticFeedback.mediumImpact();
            setState(() {
              _draggingNodeId = nodeId;
            });
          },
          onLongPressMoveUpdate: (details) {
            if (_draggingNodeId == nodeId && _scale > 0) {
              final dx = details.offsetFromOrigin.dx / _scale / 10;
              final dy = details.offsetFromOrigin.dy / _scale / 10;
              if (dx.isFinite && dy.isFinite) {
                setState(() {
                  final currentPos = _nodePositions[nodeId]!;
                  _nodePositions[nodeId] = Offset(
                    currentPos.dx + dx,
                    currentPos.dy + dy,
                  );
                });
              }
            }
          },
          onLongPressEnd: (details) {
            setState(() {
              _draggingNodeId = null;
            });
          },
          onPanStart: (details) {
            HapticFeedback.lightImpact();
            setState(() {
              _draggingNodeId = nodeId;
            });
          },
          onPanUpdate: (details) {
            if (_draggingNodeId == nodeId && _scale > 0) {
              final dx = details.delta.dx / _scale;
              final dy = details.delta.dy / _scale;
              if (dx.isFinite && dy.isFinite) {
                setState(() {
                  final currentPos = _nodePositions[nodeId]!;
                  _nodePositions[nodeId] = Offset(
                    currentPos.dx + dx,
                    currentPos.dy + dy,
                  );
                });
              }
            }
          },
          onPanEnd: (details) {
            setState(() {
              _draggingNodeId = null;
            });
          },
          child: Container(
            width: radius * 2,
            height: radius * 2,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.transparent,
            ),
          ),
        ),
      );
    }).toList();
  }

  Widget _buildDetailPanel() {
    final node = _selectedNode!;
    final name = node['name'] as String? ?? '未知';
    final relationType = node['relation_type'] as String? ?? '';
    final category = node['category'] as String? ?? 'network';
    final phone = node['phone'] as String?;
    final healthScore = node['health_score'] as int?;
    final lastInteraction = node['last_interaction_days'] as int?;

    final relationLabel = _getRelationLabel(relationType);
    final nodeColor = _getNodeColor(relationType, category);

    return Positioned(
      left: 0,
      right: 0,
      bottom: 0,
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.1),
              blurRadius: 16,
              offset: const Offset(0, -4),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Handle bar
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.divider,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            // Header
            Row(
              children: [
                // Avatar
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    color: nodeColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: nodeColor.withValues(alpha: 0.3),
                      width: 2,
                    ),
                  ),
                  child: Center(
                    child: Text(
                      name.isNotEmpty ? name.substring(0, 1) : '?',
                      style: TextStyle(
                        color: nodeColor,
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                // Info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name,
                        style: AppTextStyles.headline6.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: nodeColor.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              relationLabel,
                              style: AppTextStyles.caption.copyWith(
                                color: nodeColor,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                          if (healthScore != null) ...[
                            const SizedBox(width: 8),
                            Icon(
                              Icons.favorite,
                              size: 14,
                              color: _getHealthColor(healthScore),
                            ),
                            const SizedBox(width: 4),
                            Text(
                              '$healthScore%',
                              style: AppTextStyles.caption.copyWith(
                                color: _getHealthColor(healthScore),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                IconButton(
                  onPressed: () => setState(() => _selectedNode = null),
                  icon: const Icon(Icons.close),
                  color: AppColors.textTertiary,
                  iconSize: 20,
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Stats row
            if (lastInteraction != null || phone != null)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.background,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    if (lastInteraction != null) ...[
                      Icon(Icons.access_time, size: 16, color: AppColors.textTertiary),
                      const SizedBox(width: 6),
                      Text(
                        lastInteraction == 0
                            ? '今天联系过'
                            : '$lastInteraction天前联系',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                      if (phone != null) const SizedBox(width: 16),
                    ],
                    if (phone != null) ...[
                      Icon(Icons.phone, size: 16, color: AppColors.textTertiary),
                      const SizedBox(width: 6),
                      Text(
                        phone,
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            const SizedBox(height: 16),
            // Action buttons
            Row(
              children: [
                Expanded(
                  child: _buildActionButton(
                    icon: Icons.phone_outlined,
                    label: '打电话',
                    color: const Color(0xFF10B981),
                    onTap: () {},
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildActionButton(
                    icon: Icons.message_outlined,
                    label: '发消息',
                    color: const Color(0xFF3B82F6),
                    onTap: () {},
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildActionButton(
                    icon: Icons.person_outline,
                    label: '查看详情',
                    color: AppColors.primary,
                    onTap: () async {
                      final nodeId = _selectedNode?['id'] as String?;
                      if (nodeId != null) {
                        await context.push(Routes.memberDetail(nodeId));
                        if (context.mounted) {
                          context.read<RelationshipsBloc>().add(const RelationshipsGraphRequested());
                        }
                      }
                    },
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.lightImpact();
        onTap();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 18, color: color),
            const SizedBox(width: 6),
            Text(
              label,
              style: AppTextStyles.caption.copyWith(
                color: color,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _initializeNodePositions(List nodes) {
    final size = MediaQuery.of(context).size;
    final centerX = size.width / 2;
    final centerY = size.height / 2 - 100;

    // Group nodes by relation type for better layout
    final selfNode = nodes.where((n) => n['relation_type'] == 'self').toList();
    final spouseNodes = nodes.where((n) =>
      (n['relation_type'] as String?)?.contains('spouse') == true ||
      (n['relation_type'] as String?)?.contains('partner') == true
    ).toList();
    final parentNodes = nodes.where((n) {
      final rt = n['relation_type'] as String? ?? '';
      return rt.contains('father') || rt.contains('mother') || rt == 'parent';
    }).toList();
    final inLawNodes = nodes.where((n) {
      final rt = n['relation_type'] as String? ?? '';
      return rt.contains('in_law') || rt.contains('inlaw');
    }).toList();
    final childNodes = nodes.where((n) {
      final rt = n['relation_type'] as String? ?? '';
      return rt.contains('child') || rt.contains('son') || rt.contains('daughter');
    }).toList();
    final siblingNodes = nodes.where((n) {
      final rt = n['relation_type'] as String? ?? '';
      return rt.contains('sibling') || rt.contains('brother') || rt.contains('sister');
    }).toList();
    final grandparentNodes = nodes.where((n) {
      final rt = n['relation_type'] as String? ?? '';
      return rt.contains('grandparent') || rt.contains('grandmother') || rt.contains('grandfather');
    }).toList();
    final otherNodes = nodes.where((n) {
      final rt = n['relation_type'] as String? ?? '';
      final id = n['id'] as String;
      return !_nodePositions.containsKey(id) &&
             rt != 'self' &&
             !rt.contains('spouse') && !rt.contains('partner') &&
             !rt.contains('father') && !rt.contains('mother') && rt != 'parent' &&
             !rt.contains('in_law') && !rt.contains('inlaw') &&
             !rt.contains('child') && !rt.contains('son') && !rt.contains('daughter') &&
             !rt.contains('sibling') && !rt.contains('brother') && !rt.contains('sister') &&
             !rt.contains('grandparent') && !rt.contains('grandmother') && !rt.contains('grandfather');
    }).toList();

    // Place self at center
    for (final node in selfNode) {
      _nodePositions[node['id'] as String] = Offset(centerX, centerY);
    }

    // Place spouse to the right
    _placeNodesInArc(spouseNodes, centerX, centerY, 100, 0, 0.3);

    // Place parents above
    _placeNodesInArc(parentNodes, centerX, centerY, 130, -math.pi / 2, 0.4);

    // Place in-laws above-right
    _placeNodesInArc(inLawNodes, centerX, centerY, 160, -math.pi / 4, 0.4);

    // Place children below
    _placeNodesInArc(childNodes, centerX, centerY, 130, math.pi / 2, 0.5);

    // Place siblings to the left
    _placeNodesInArc(siblingNodes, centerX, centerY, 120, math.pi, 0.4);

    // Place grandparents further above
    _placeNodesInArc(grandparentNodes, centerX, centerY, 200, -math.pi / 2, 0.6);

    // Place others around the perimeter
    _placeNodesInArc(otherNodes, centerX, centerY, 200, math.pi * 1.2, 1.2);

    setState(() {
      _isInitialized = true;
    });
  }

  void _placeNodesInArc(
    List nodes,
    double centerX,
    double centerY,
    double radius,
    double centerAngle,
    double arcSpan,
  ) {
    if (nodes.isEmpty) return;

    final count = nodes.length;
    for (int i = 0; i < count; i++) {
      final angle = count == 1
          ? centerAngle
          : centerAngle - arcSpan / 2 + (arcSpan / (count - 1)) * i;
      final nodeId = nodes[i]['id'] as String;
      _nodePositions[nodeId] = Offset(
        centerX + radius * math.cos(angle),
        centerY + radius * math.sin(angle),
      );
    }
  }

  void _resetView() {
    setState(() {
      _panOffset = Offset.zero;
      _scale = 1.0;
      _selectedNode = null;
    });
  }

  void _autoLayout() {
    setState(() {
      _isInitialized = false;
      _nodePositions.clear();
    });
  }

  String _getRelationLabel(String relationType) =>
      RelationUtils.getRelationLabel(relationType);

  Color _getNodeColor(String relationType, String category) {
    if (relationType == 'self') return AppColors.primary;
    if (relationType.contains('spouse') || relationType.contains('partner')) {
      return const Color(0xFFEC4899);
    }
    if (relationType.contains('parent') || relationType.contains('father') || relationType.contains('mother')) {
      return const Color(0xFF8B5CF6);
    }
    if (relationType.contains('child') || relationType.contains('son') || relationType.contains('daughter')) {
      return const Color(0xFF10B981);
    }
    if (relationType.contains('sibling') || relationType.contains('brother') || relationType.contains('sister')) {
      return const Color(0xFF3B82F6);
    }
    if (relationType.contains('grandparent') || relationType.contains('grandmother') || relationType.contains('grandfather')) {
      return const Color(0xFFF59E0B);
    }
    if (relationType.contains('in_law') || relationType.contains('inlaw')) {
      return const Color(0xFF06B6D4);
    }
    if (category == 'family') return const Color(0xFFF59E0B);
    return const Color(0xFF6B7280);
  }

  Color _getHealthColor(int score) {
    if (score >= 70) return const Color(0xFF10B981);
    if (score >= 40) return const Color(0xFFF59E0B);
    return const Color(0xFFEF4444);
  }
}

/// Custom painter for the relationship graph
class _GraphPainter extends CustomPainter {
  final List nodes;
  final List edges;
  final Map<String, Offset> nodePositions;
  final String? selectedNodeId;
  final Offset panOffset;
  final double scale;

  _GraphPainter({
    required this.nodes,
    required this.edges,
    required this.nodePositions,
    this.selectedNodeId,
    required this.panOffset,
    required this.scale,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (nodePositions.isEmpty || !scale.isFinite || scale <= 0) return;

    // Draw edges first
    for (final edge in edges) {
      final sourceId = edge['source'] as String;
      final targetId = edge['target'] as String;
      final relationType = edge['relation_type'] as String? ?? '';

      final sourcePos = nodePositions[sourceId];
      final targetPos = nodePositions[targetId];

      if (sourcePos != null && targetPos != null) {
        final adjustedSource = _adjustPosition(sourcePos);
        final adjustedTarget = _adjustPosition(targetPos);
        _drawEdge(canvas, adjustedSource, adjustedTarget, relationType);
      }
    }

    // Draw nodes
    for (final node in nodes) {
      final nodeId = node['id'] as String;
      final position = nodePositions[nodeId];
      if (position == null) continue;

      final adjustedPos = _adjustPosition(position);
      _drawNode(canvas, node, adjustedPos, nodeId == selectedNodeId);
    }
  }

  void _drawEdge(Canvas canvas, Offset source, Offset target, String relationType) {
    Color edgeColor;
    double strokeWidth = 2.0;

    if (relationType.contains('spouse') || relationType.contains('partner')) {
      edgeColor = const Color(0xFFEC4899);
      strokeWidth = 3.0;
    } else if (relationType.contains('parent') || relationType.contains('child') ||
               relationType.contains('father') || relationType.contains('mother') ||
               relationType.contains('son') || relationType.contains('daughter')) {
      edgeColor = const Color(0xFF8B5CF6);
      strokeWidth = 2.5;
    } else if (relationType.contains('sibling') || relationType.contains('brother') ||
               relationType.contains('sister')) {
      edgeColor = const Color(0xFF3B82F6);
      strokeWidth = 2.5;
    } else if (relationType.contains('grandparent') || relationType.contains('grandfather') ||
               relationType.contains('grandmother') || relationType.contains('grandchild')) {
      edgeColor = const Color(0xFFF59E0B);
    } else if (relationType.contains('in_law') || relationType.contains('inlaw')) {
      edgeColor = const Color(0xFF06B6D4);
    } else if (relationType.contains('friend')) {
      edgeColor = const Color(0xFF10B981);
    } else if (relationType.contains('colleague') || relationType.contains('boss') ||
               relationType.contains('peer') || relationType.contains('mentor')) {
      edgeColor = const Color(0xFF6366F1);
    } else {
      edgeColor = const Color(0xFF9CA3AF);
      strokeWidth = 1.5;
    }

    final edgePaint = Paint()
      ..color = edgeColor.withValues(alpha: 0.6)
      ..strokeWidth = strokeWidth * scale
      ..style = PaintingStyle.stroke;

    canvas.drawLine(source, target, edgePaint);
  }

  Offset _adjustPosition(Offset position) {
    return Offset(
      position.dx * scale + panOffset.dx,
      position.dy * scale + panOffset.dy,
    );
  }

  void _drawNode(
    Canvas canvas,
    Map<String, dynamic> node,
    Offset position,
    bool isSelected,
  ) {
    final name = node['name'] as String? ?? '?';
    final category = node['category'] as String? ?? 'network';
    final importance = node['importance'] as int? ?? 3;
    final relationType = node['relation_type'] as String? ?? '';

    // Node color based on relation type
    Color nodeColor;
    if (relationType == 'self') {
      nodeColor = AppColors.primary;
    } else if (relationType.contains('spouse') || relationType.contains('partner')) {
      nodeColor = const Color(0xFFEC4899);
    } else if (relationType.contains('parent') || relationType.contains('father') || relationType.contains('mother')) {
      nodeColor = const Color(0xFF8B5CF6);
    } else if (relationType.contains('child') || relationType.contains('son') || relationType.contains('daughter')) {
      nodeColor = const Color(0xFF10B981);
    } else if (relationType.contains('sibling') || relationType.contains('brother') || relationType.contains('sister')) {
      nodeColor = const Color(0xFF3B82F6);
    } else if (relationType.contains('grandparent') || relationType.contains('grandmother') || relationType.contains('grandfather')) {
      nodeColor = const Color(0xFFF59E0B);
    } else if (relationType.contains('in_law') || relationType.contains('inlaw')) {
      nodeColor = const Color(0xFF06B6D4);
    } else if (category == 'family') {
      nodeColor = const Color(0xFFF59E0B);
    } else {
      nodeColor = const Color(0xFF6B7280);
    }

    final radius = (18.0 + importance * 3) * scale;

    // Draw shadow
    final shadowPaint = Paint()
      ..color = Colors.black.withValues(alpha: 0.1)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);
    canvas.drawCircle(position.translate(0, 2 * scale), radius, shadowPaint);

    // Draw glow for selected node
    if (isSelected) {
      final glowPaint = Paint()
        ..color = nodeColor.withValues(alpha: 0.4)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, 16 * scale);
      canvas.drawCircle(position, radius + 10 * scale, glowPaint);
    }

    // Draw white background
    final bgPaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;
    canvas.drawCircle(position, radius, bgPaint);

    // Draw colored border
    final borderPaint = Paint()
      ..color = nodeColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = (isSelected ? 4 : 3) * scale;
    canvas.drawCircle(position, radius, borderPaint);

    // Draw name initial
    final initial = name.isNotEmpty ? name.substring(0, 1) : '?';
    final textPainter = TextPainter(
      text: TextSpan(
        text: initial,
        style: TextStyle(
          color: nodeColor,
          fontSize: radius * 0.75,
          fontWeight: FontWeight.bold,
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    textPainter.layout();
    textPainter.paint(
      canvas,
      Offset(
        position.dx - textPainter.width / 2,
        position.dy - textPainter.height / 2,
      ),
    );

    // Draw name label below
    final labelPainter = TextPainter(
      text: TextSpan(
        text: name,
        style: TextStyle(
          color: AppColors.textPrimary,
          fontSize: 11 * scale,
          fontWeight: FontWeight.w500,
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    labelPainter.layout();
    labelPainter.paint(
      canvas,
      Offset(
        position.dx - labelPainter.width / 2,
        position.dy + radius + 6 * scale,
      ),
    );
  }

  @override
  bool shouldRepaint(covariant _GraphPainter oldDelegate) {
    return oldDelegate.selectedNodeId != selectedNodeId ||
        oldDelegate.panOffset != panOffset ||
        oldDelegate.scale != scale ||
        oldDelegate.nodePositions != nodePositions;
  }
}
