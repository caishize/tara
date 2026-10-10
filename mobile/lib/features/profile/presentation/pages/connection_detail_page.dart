import 'package:flutter/material.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../data/datasources/connections_remote_datasource.dart';
import '../../data/models/connection_model.dart';
import 'package:go_router/go_router.dart';

class ConnectionDetailPage extends StatefulWidget {
  final String connectionId;
  final UserConnection? connection;

  const ConnectionDetailPage({
    super.key,
    required this.connectionId,
    this.connection,
  });

  @override
  State<ConnectionDetailPage> createState() => _ConnectionDetailPageState();
}

class _ConnectionDetailPageState extends State<ConnectionDetailPage> {
  late ConnectionsRemoteDataSource _dataSource;
  UserConnection? _connection;
  bool _isLoading = false;
  bool _isSyncing = false;
  Set<String> _enabledScopes = {};

  @override
  void initState() {
    super.initState();
    _dataSource = getIt<ConnectionsRemoteDataSource>();
    _connection = widget.connection;
    if (_connection != null) {
      _enabledScopes = _connection!.scopes.toSet();
    } else {
      _loadConnection();
    }
  }

  Future<void> _loadConnection() async {
    setState(() => _isLoading = true);
    try {
      final connections = await _dataSource.fetchConnections();
      final found = connections.where((c) => c.id == widget.connectionId);
      if (found.isNotEmpty && mounted) {
        setState(() {
          _connection = found.first;
          _enabledScopes = _connection!.scopes.toSet();
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _triggerSync() async {
    setState(() => _isSyncing = true);
    try {
      await _dataSource.syncConnection(widget.connectionId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('\u540c\u6b65\u5df2\u89e6\u53d1'),
            backgroundColor: AppColors.success,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('\u540c\u6b65\u5931\u8d25: $e'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isSyncing = false);
    }
  }

  Future<void> _disconnect() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('\u786e\u8ba4\u65ad\u5f00\u8fde\u63a5'),
        content: Text(
          '\u65ad\u5f00\u540e\u5c06\u4e0d\u518d\u540c\u6b65 ${_connection?.displayName ?? ''} \u7684\u6570\u636e\u3002\u786e\u8ba4\u65ad\u5f00\uff1f',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('\u53d6\u6d88'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: FilledButton.styleFrom(backgroundColor: AppColors.error),
            child: const Text('\u65ad\u5f00\u8fde\u63a5'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      await _dataSource.disconnectProvider(widget.connectionId);
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('\u65ad\u5f00\u5931\u8d25: $e'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(_connection?.displayName ?? '\u8fde\u63a5\u8be6\u60c5'),
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _connection == null
              ? const Center(child: Text('\u8fde\u63a5\u4e0d\u5b58\u5728'))
              : _buildContent(),
    );
  }

  Widget _buildContent() {
    final conn = _connection!;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Provider header
        _buildProviderHeader(conn),
        const SizedBox(height: 24),

        // Scopes section
        _buildScopesSection(conn),
        const SizedBox(height: 24),

        // Sync info
        _buildSyncSection(conn),
        const SizedBox(height: 24),

        // Sync frequency
        _buildSyncFrequencySection(conn),
        const SizedBox(height: 32),

        // Manual sync button
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: _isSyncing ? null : _triggerSync,
            icon: _isSyncing
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.sync),
            label: Text(_isSyncing ? '\u540c\u6b65\u4e2d...' : '\u624b\u52a8\u540c\u6b65'),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.primary,
              side: const BorderSide(color: AppColors.primary),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
        const SizedBox(height: 16),

        // Disconnect button
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: _disconnect,
            icon: const Icon(Icons.link_off),
            label: const Text('\u65ad\u5f00\u8fde\u63a5'),
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.error,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildProviderHeader(UserConnection conn) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            CircleAvatar(
              radius: 28,
              backgroundColor: AppColors.chipBackground,
              backgroundImage:
                  conn.iconUrl != null ? NetworkImage(conn.iconUrl!) : null,
              child: conn.iconUrl == null
                  ? Text(
                      conn.providerName.isNotEmpty
                          ? conn.providerName[0].toUpperCase()
                          : '?',
                      style: AppTextStyles.headline4.copyWith(
                        color: AppColors.primary,
                      ),
                    )
                  : null,
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(conn.displayName, style: AppTextStyles.headline5),
                  const SizedBox(height: 4),
                  Text(
                    conn.providerType,
                    style: AppTextStyles.caption,
                  ),
                ],
              ),
            ),
            _buildStatusChip(conn),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusChip(UserConnection conn) {
    Color color;
    String label;

    if (conn.hasError) {
      color = AppColors.error;
      label = '\u5f02\u5e38';
    } else if (conn.isConnected) {
      color = AppColors.success;
      label = '\u5df2\u8fde\u63a5';
    } else {
      color = AppColors.textTertiary;
      label = '\u672a\u8fde\u63a5';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: AppTextStyles.caption.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildScopesSection(UserConnection conn) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('\u6743\u9650\u8303\u56f4', style: AppTextStyles.headline6),
            const SizedBox(height: 12),
            if (conn.scopes.isEmpty)
              Text(
                '\u65e0\u6743\u9650\u4fe1\u606f',
                style: AppTextStyles.bodyText2,
              )
            else
              ...conn.scopes.map((scope) => CheckboxListTile(
                    title: Text(scope, style: AppTextStyles.bodyText2),
                    value: _enabledScopes.contains(scope),
                    onChanged: (value) {
                      setState(() {
                        if (value == true) {
                          _enabledScopes = {..._enabledScopes, scope};
                        } else {
                          _enabledScopes = _enabledScopes
                              .where((s) => s != scope)
                              .toSet();
                        }
                      });
                    },
                    activeColor: AppColors.primary,
                    controlAffinity: ListTileControlAffinity.leading,
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                  )),
          ],
        ),
      ),
    );
  }

  Widget _buildSyncSection(UserConnection conn) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('\u540c\u6b65\u4fe1\u606f', style: AppTextStyles.headline6),
            const SizedBox(height: 12),
            _InfoRow(
              label: '\u4e0a\u6b21\u540c\u6b65',
              value: conn.lastSyncAt != null
                  ? _formatDateTime(conn.lastSyncAt!)
                  : '\u4ece\u672a\u540c\u6b65',
            ),
            if (conn.lastError != null) ...[
              const SizedBox(height: 8),
              _InfoRow(
                label: '\u6700\u8fd1\u9519\u8bef',
                value: conn.lastError!,
                valueColor: AppColors.error,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSyncFrequencySection(UserConnection conn) {
    final frequency = conn.syncFrequency ?? 'daily';
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('\u540c\u6b65\u9891\u7387', style: AppTextStyles.headline6),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                _FrequencyChip(
                  label: '\u5b9e\u65f6',
                  value: 'realtime',
                  selected: frequency == 'realtime',
                ),
                _FrequencyChip(
                  label: '\u6bcf\u5c0f\u65f6',
                  value: 'hourly',
                  selected: frequency == 'hourly',
                ),
                _FrequencyChip(
                  label: '\u6bcf\u5929',
                  value: 'daily',
                  selected: frequency == 'daily',
                ),
                _FrequencyChip(
                  label: '\u6bcf\u5468',
                  value: 'weekly',
                  selected: frequency == 'weekly',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _formatDateTime(DateTime dt) {
    final local = dt.toLocal();
    return '${local.year}-${local.month.toString().padLeft(2, '0')}-'
        '${local.day.toString().padLeft(2, '0')} '
        '${local.hour.toString().padLeft(2, '0')}:'
        '${local.minute.toString().padLeft(2, '0')}';
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;

  const _InfoRow({
    required this.label,
    required this.value,
    this.valueColor,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: AppTextStyles.bodyText2),
        Flexible(
          child: Text(
            value,
            style: AppTextStyles.bodyText2.copyWith(
              color: valueColor ?? AppColors.textPrimary,
              fontWeight: FontWeight.w500,
            ),
            textAlign: TextAlign.end,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}

class _FrequencyChip extends StatelessWidget {
  final String label;
  final String value;
  final bool selected;

  const _FrequencyChip({
    required this.label,
    required this.value,
    required this.selected,
  });

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      selectedColor: AppColors.primary.withValues(alpha: 0.15),
      backgroundColor: AppColors.chipBackground,
      labelStyle: AppTextStyles.caption.copyWith(
        color: selected ? AppColors.primary : AppColors.textSecondary,
        fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      side: BorderSide(
        color: selected ? AppColors.primary : Colors.transparent,
      ),
      onSelected: (_) {
        // Frequency selection is visual-only for now;
        // could be extended to call updateConnection
      },
    );
  }
}
