import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../domain/entities/itinerary_version.dart';
import '../../data/models/itinerary_version_model.dart';
import '../../../../core/network/api_client.dart';
import '../../../../app/di/injection.dart';

class ItineraryVersionsPage extends StatefulWidget {
  final String tripId;
  final String? tripName;

  const ItineraryVersionsPage({
    super.key,
    required this.tripId,
    this.tripName,
  });

  @override
  State<ItineraryVersionsPage> createState() => _ItineraryVersionsPageState();
}

class _ItineraryVersionsPageState extends State<ItineraryVersionsPage> {
  List<ItineraryVersionSummary> _versions = [];
  String? _activeVersionId;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadVersions();
  }

  Future<void> _loadVersions() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final apiClient = getIt<ApiClient>();
      final response = await apiClient.get(
        '/trips/plans/${widget.tripId}/versions',
      );

      final items = (response['items'] as List?)
              ?.map((v) => ItineraryVersionSummaryModel.fromJson(v))
              .toList() ??
          [];

      setState(() {
        _versions = items;
        _activeVersionId = response['active_version_id']?.toString();
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _activateVersion(ItineraryVersionSummary version) async {
    try {
      final apiClient = getIt<ApiClient>();
      await apiClient.post(
        '/trips/plans/${widget.tripId}/versions/activate',
        data: {'version_id': version.id},
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已切换到 ${version.displayName}')),
      );

      _loadVersions();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('切换失败: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _deleteVersion(ItineraryVersionSummary version) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认删除'),
        content: Text('确定要删除 "${version.displayName}" 吗？此操作不可恢复。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('删除'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final apiClient = getIt<ApiClient>();
      await apiClient.delete(
        '/trips/plans/${widget.tripId}/versions/${version.id}',
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已删除 ${version.displayName}')),
      );

      _loadVersions();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('删除失败: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _renameVersion(ItineraryVersionSummary version) async {
    final controller = TextEditingController(text: version.versionName);

    final newName = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('重命名方案'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            labelText: '方案名称',
            hintText: '输入新名称',
          ),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, controller.text),
            child: const Text('确定'),
          ),
        ],
      ),
    );

    if (newName == null || newName.isEmpty) return;

    try {
      final apiClient = getIt<ApiClient>();
      await apiClient.put(
        '/trips/plans/${widget.tripId}/versions/${version.id}',
        data: {'version_name': newName},
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('已更新名称')),
      );

      _loadVersions();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('更新失败: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.tripName != null ? '${widget.tripName} - 版本管理' : '行程版本管理'),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 48, color: Colors.red[300]),
            const SizedBox(height: 16),
            Text('加载失败: $_error'),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadVersions,
              child: const Text('重试'),
            ),
          ],
        ),
      );
    }

    if (_versions.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.history, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            const Text('暂无行程版本'),
            const SizedBox(height: 8),
            Text(
              '生成行程后会自动保存版本',
              style: TextStyle(color: Colors.grey[600]),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadVersions,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _versions.length,
        itemBuilder: (context, index) {
          final version = _versions[index];
          final isActive = version.id == _activeVersionId;

          return _VersionCard(
            version: version,
            isActive: isActive,
            onActivate: () => _activateVersion(version),
            onRename: () => _renameVersion(version),
            onDelete: isActive ? null : () => _deleteVersion(version),
          );
        },
      ),
    );
  }
}

class _VersionCard extends StatelessWidget {
  final ItineraryVersionSummary version;
  final bool isActive;
  final VoidCallback onActivate;
  final VoidCallback onRename;
  final VoidCallback? onDelete;

  const _VersionCard({
    required this.version,
    required this.isActive,
    required this.onActivate,
    required this.onRename,
    this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final dateFormat = DateFormat('MM/dd HH:mm');

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: isActive
            ? BorderSide(color: theme.colorScheme.primary, width: 2)
            : BorderSide.none,
      ),
      child: InkWell(
        onTap: isActive ? null : onActivate,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header row
              Row(
                children: [
                  Expanded(
                    child: Row(
                      children: [
                        Text(
                          version.displayName,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (isActive) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: theme.colorScheme.primary,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              '当前',
                              style: TextStyle(
                                color: theme.colorScheme.onPrimary,
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  PopupMenuButton<String>(
                    onSelected: (value) {
                      switch (value) {
                        case 'rename':
                          onRename();
                          break;
                        case 'delete':
                          onDelete?.call();
                          break;
                      }
                    },
                    itemBuilder: (context) => [
                      const PopupMenuItem(
                        value: 'rename',
                        child: Row(
                          children: [
                            Icon(Icons.edit, size: 20),
                            SizedBox(width: 8),
                            Text('重命名'),
                          ],
                        ),
                      ),
                      if (onDelete != null)
                        const PopupMenuItem(
                          value: 'delete',
                          child: Row(
                            children: [
                              Icon(Icons.delete, size: 20, color: Colors.red),
                              SizedBox(width: 8),
                              Text('删除', style: TextStyle(color: Colors.red)),
                            ],
                          ),
                        ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 8),
              // Style tags
              if (version.styleDisplayNames.isNotEmpty)
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: version.styleDisplayNames
                      .map(
                        (style) => Chip(
                          label: Text(style),
                          labelStyle: const TextStyle(fontSize: 12),
                          padding: EdgeInsets.zero,
                          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          visualDensity: VisualDensity.compact,
                        ),
                      )
                      .toList(),
                ),
              const SizedBox(height: 12),
              // Stats row
              Row(
                children: [
                  _StatItem(
                    icon: Icons.calendar_today,
                    label: '${version.totalDays}天',
                  ),
                  const SizedBox(width: 16),
                  _StatItem(
                    icon: Icons.list,
                    label: '${version.totalActivities}项活动',
                  ),
                  const SizedBox(width: 16),
                  if (version.totalEstimatedCost != null)
                    _StatItem(
                      icon: Icons.attach_money,
                      label: '¥${version.totalEstimatedCost!.toStringAsFixed(0)}',
                    ),
                ],
              ),
              const SizedBox(height: 8),
              // Date
              Text(
                '创建于 ${dateFormat.format(version.createdAt)}',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey[600],
                ),
              ),
              // Activate button (if not active)
              if (!isActive) ...[
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: onActivate,
                    child: const Text('切换到此版本'),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  final IconData icon;
  final String label;

  const _StatItem({
    required this.icon,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: Colors.grey[600]),
        const SizedBox(width: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 13,
            color: Colors.grey[700],
          ),
        ),
      ],
    );
  }
}
