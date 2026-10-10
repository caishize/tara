import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/di/injection.dart';
import '../../../../app/theme/app_colors.dart';
import '../../data/models/connection_model.dart';
import '../bloc/connections_bloc.dart';

/// Data connections management page matching the "数据连接管理" prototype.
/// Two sections: 外部数据连接 (external data sources) + MCP 服务 (MCP services).
/// Main list shows only connected items; "添加" opens a picker for available providers.
class ConnectionsPage extends StatelessWidget {
  const ConnectionsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          getIt<ConnectionsBloc>()..add(const LoadConnections()),
      child: const _ConnectionsPageContent(),
    );
  }
}

// ──────── icon/color helpers ────────

const _providerIconMap = <String, IconData>{
  'calendar': Icons.calendar_today,
  'google_calendar': Icons.calendar_today,
  'apple_calendar': Icons.calendar_today,
  'outlook_calendar': Icons.calendar_today,
  'email': Icons.mail_outline,
  'imap': Icons.mail_outline,
  'gmail': Icons.mail_outline,
  'outlook_mail': Icons.mail_outline,
  'qq_mail': Icons.mail_outline,
  'contacts': Icons.contacts_outlined,
  'notes': Icons.note_outlined,
  'notion': Icons.note_outlined,
  'apple_notes': Icons.note_outlined,
  'weather': Icons.cloud_outlined,
  'search': Icons.search,
  'web_search': Icons.search,
  'document': Icons.description_outlined,
  'doc_parser': Icons.description_outlined,
  'transport': Icons.directions_car_outlined,
  'amap': Icons.directions_car_outlined,
  'shopping': Icons.shopping_cart_outlined,
  'jd': Icons.shopping_cart_outlined,
  'smart_home': Icons.home_outlined,
  'mi_home': Icons.home_outlined,
};

IconData _iconFor(String key) =>
    _providerIconMap[key.toLowerCase()] ?? Icons.extension_outlined;

const _providerColorMap = <String, (Color bg, Color fg)>{
  'calendar': (AppColors.accentGreenLight, AppColors.accentGreen),
  'google_calendar': (AppColors.accentGreenLight, AppColors.accentGreen),
  'apple_calendar': (AppColors.accentGreenLight, AppColors.accentGreen),
  'outlook_calendar': (AppColors.accentGreenLight, AppColors.accentGreen),
  'email': (AppColors.accentWarmLight, AppColors.accentWarm),
  'imap': (AppColors.accentWarmLight, AppColors.accentWarm),
  'gmail': (AppColors.accentWarmLight, AppColors.accentWarm),
  'outlook_mail': (AppColors.accentWarmLight, AppColors.accentWarm),
  'qq_mail': (AppColors.accentWarmLight, AppColors.accentWarm),
  'contacts': (Color(0xFFEDECEA), AppColors.textSecondary),
  'notes': (Color(0xFFFFF8E1), Color(0xFFF9A825)),
  'notion': (Color(0xFFFFF8E1), Color(0xFFF9A825)),
  'apple_notes': (Color(0xFFFFF8E1), Color(0xFFF9A825)),
  'weather': (Color(0xFFE8EAF6), Color(0xFF5C6BC0)),
  'search': (Color(0xFFFFF3E0), Color(0xFFEF6C00)),
  'web_search': (Color(0xFFFFF3E0), Color(0xFFEF6C00)),
  'document': (Color(0xFFEDECEA), AppColors.textTertiary),
  'doc_parser': (Color(0xFFEDECEA), AppColors.textTertiary),
  'transport': (Color(0xFFE3F2FD), Color(0xFF1976D2)),
  'amap': (Color(0xFFE3F2FD), Color(0xFF1976D2)),
  'shopping': (Color(0xFFFCE4EC), Color(0xFFE91E63)),
  'jd': (Color(0xFFFCE4EC), Color(0xFFE91E63)),
  'smart_home': (Color(0xFFE8F5E9), Color(0xFF388E3C)),
  'mi_home': (Color(0xFFE8F5E9), Color(0xFF388E3C)),
};

(Color bg, Color fg) _colorsFor(String key) =>
    _providerColorMap[key.toLowerCase()] ??
    (const Color(0xFFEDECEA), AppColors.textSecondary);

bool _isMcpType(String providerType) =>
    providerType.toLowerCase() == 'mcp' ||
    providerType.toLowerCase() == 'mcp_service' ||
    providerType.toLowerCase() == 'custom';

// ──────── page content ────────

class _ConnectionsPageContent extends StatelessWidget {
  const _ConnectionsPageContent();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => context.pop(),
        ),
        title: const Text(
          '数据连接管理',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
      ),
      body: BlocConsumer<ConnectionsBloc, ConnectionsState>(
        listener: (context, state) {
          if (state is ConnectionsError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: AppColors.error,
              ),
            );
          }
        },
        builder: (context, state) {
          if (state is ConnectionsLoading) {
            return const Center(child: CircularProgressIndicator());
          }

          if (state is ConnectionsLoaded) {
            return _buildLoadedContent(context, state);
          }

          return const Center(child: CircularProgressIndicator());
        },
      ),
    );
  }

  Widget _buildLoadedContent(BuildContext context, ConnectionsLoaded state) {
    // Only show connected items in the main list
    final extConnections = state.connections
        .where((c) => !_isMcpType(c.providerType))
        .toList();
    final mcpConnections = state.connections
        .where((c) => _isMcpType(c.providerType))
        .toList();

    return RefreshIndicator(
      onRefresh: () async {
        context.read<ConnectionsBloc>().add(const LoadConnections());
      },
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Section 1: External data connections
          _buildSectionLabel('外部数据连接'),
          const SizedBox(height: 8),
          _buildExternalGroup(context, extConnections, state),
          const SizedBox(height: 20),

          // Section 2: MCP services
          _buildSectionLabel('MCP 服务'),
          const SizedBox(height: 8),
          _buildMcpGroup(context, mcpConnections),
          const SizedBox(height: 20),

          // MCP info card
          _buildMcpInfoCard(),
        ],
      ),
    );
  }

  Widget _buildSectionLabel(String label) {
    return Text(
      label,
      style: const TextStyle(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: Color(0xFF6D6C6A),
      ),
    );
  }

  // ──────── External data connections group ────────

  Widget _buildExternalGroup(
    BuildContext context,
    List<UserConnection> connected,
    ConnectionsLoaded state,
  ) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          // Only connected external services
          if (connected.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
              child: Column(
                children: [
                  Icon(
                    Icons.link_off,
                    size: 32,
                    color: AppColors.textTertiary.withValues(alpha: 0.5),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    '暂无已连接的数据源',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppColors.textTertiary,
                    ),
                  ),
                ],
              ),
            ),
          for (int i = 0; i < connected.length; i++) ...[
            _buildConnectionRow(connected[i]),
            if (i < connected.length - 1) _buildDivider(leftPadding: 64),
          ],

          if (connected.isNotEmpty) _buildDivider(leftPadding: 16),

          // Add data source button — opens picker for available providers
          _buildAddButton(
            icon: Icons.add_circle_outline,
            label: '添加数据源',
            onTap: () => _showAddExternalDialog(context, state),
          ),
        ],
      ),
    );
  }

  Widget _buildConnectionRow(UserConnection conn) {
    final key = conn.providerName.isNotEmpty
        ? conn.providerName
        : conn.providerType;
    final colors = _colorsFor(key);
    final icon = _iconFor(key);

    String subtitle;
    if (conn.hasError) {
      subtitle = conn.lastError ?? '连接异常';
    } else if (conn.lastSyncAt != null) {
      subtitle = '上次同步: ${_formatRelativeTime(conn.lastSyncAt!)}';
    } else {
      subtitle = '已连接';
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: colors.$1,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 18, color: colors.$2),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  conn.displayName,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 12,
                    color: conn.hasError
                        ? AppColors.error
                        : AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          _buildStatusBadge(conn.isConnected, conn.hasError),
        ],
      ),
    );
  }

  Widget _buildStatusBadge(bool isConnected, bool hasError) {
    Color bgColor;
    Color fgColor;
    String label;

    if (hasError) {
      bgColor = AppColors.error.withValues(alpha: 0.12);
      fgColor = AppColors.error;
      label = '异常';
    } else if (isConnected) {
      bgColor = AppColors.accentGreenLight;
      fgColor = AppColors.accentGreen;
      label = '已连接';
    } else {
      bgColor = const Color(0xFFEDECEA);
      fgColor = AppColors.textTertiary;
      label = '未连接';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: fgColor,
        ),
      ),
    );
  }

  // ──────── MCP services group ────────

  Widget _buildMcpGroup(
    BuildContext context,
    List<UserConnection> connected,
  ) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          // Only connected MCP services
          if (connected.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
              child: Column(
                children: [
                  Icon(
                    Icons.electrical_services_outlined,
                    size: 32,
                    color: AppColors.textTertiary.withValues(alpha: 0.5),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    '暂无已连接的 MCP 服务',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppColors.textTertiary,
                    ),
                  ),
                ],
              ),
            ),
          for (int i = 0; i < connected.length; i++) ...[
            _buildMcpConnectionRow(connected[i]),
            if (i < connected.length - 1) _buildDivider(leftPadding: 64),
          ],

          if (connected.isNotEmpty) _buildDivider(leftPadding: 16),

          // Add MCP service button
          _buildAddButton(
            icon: Icons.add_circle_outline,
            label: '添加 MCP 服务',
            onTap: () => _showAddMcpDialog(context),
          ),
        ],
      ),
    );
  }

  Widget _buildMcpConnectionRow(UserConnection conn) {
    final key = conn.providerName.isNotEmpty
        ? conn.providerName
        : conn.providerType;
    final colors = _colorsFor(key);
    final icon = _iconFor(key);

    String subtitle;
    if (conn.hasError) {
      subtitle = conn.lastError ?? '连接异常';
    } else if (conn.lastSyncAt != null) {
      subtitle = '上次同步: ${_formatRelativeTime(conn.lastSyncAt!)}';
    } else {
      subtitle = conn.syncFrequency ?? '已连接';
    }

    return InkWell(
      onTap: () {
        // TODO: Navigate to MCP service detail
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: colors.$1,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, size: 18, color: colors.$2),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    conn.displayName,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 12,
                      color: conn.hasError
                          ? AppColors.error
                          : AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            // Status dot
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: conn.isConnected
                    ? AppColors.accentGreen
                    : (conn.hasError ? AppColors.error : AppColors.textTertiary),
              ),
            ),
            const SizedBox(width: 12),
            const Icon(
              Icons.chevron_right,
              size: 18,
              color: AppColors.textTertiary,
            ),
          ],
        ),
      ),
    );
  }

  // ──────── Shared widgets ────────

  Widget _buildAddButton({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 18, color: AppColors.accentGreen),
            const SizedBox(width: 8),
            Text(
              label,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: AppColors.accentGreen,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDivider({double leftPadding = 16}) {
    return Padding(
      padding: EdgeInsets.only(left: leftPadding, right: 16),
      child: const Divider(height: 1, thickness: 1, color: Color(0xFFE5E4E1)),
    );
  }

  Widget _buildMcpInfoCard() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.accentGreenLight,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: EdgeInsets.only(top: 2),
            child: Icon(
              Icons.info_outline,
              size: 16,
              color: AppColors.accentGreen,
            ),
          ),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'MCP (Model Context Protocol) 允许 AI 助手通过标准协议连接外部工具和数据源，扩展助手的能力范围。',
              style: TextStyle(
                fontSize: 12,
                color: AppColors.accentGreen,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ──────── Dialogs ────────

  void _showConnectConfirmation(
      BuildContext context, AvailableProvider provider) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('连接 ${provider.displayName}'),
        content: Text(
          '确认要连接 ${provider.displayName} 吗？\n\n'
          '${provider.description}'
          '${provider.defaultScopes.isNotEmpty ? '\n\n将获取以下权限:\n${provider.defaultScopes.map((s) => '• $s').join('\n')}' : ''}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              context
                  .read<ConnectionsBloc>()
                  .add(ConnectProvider(provider.providerName));
            },
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.accentGreen,
            ),
            child: const Text('确认连接'),
          ),
        ],
      ),
    );
  }

  void _showAddExternalDialog(BuildContext context, ConnectionsLoaded state) {
    final connectedNames =
        state.connections.map((c) => c.providerName).toSet();
    final available = state.availableProviders
        .where((p) =>
            !_isMcpType(p.providerType) &&
            !connectedNames.contains(p.providerName))
        .toList();

    if (available.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('暂无可添加的数据源')),
      );
      return;
    }

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.6,
      ),
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Handle bar
            Container(
              margin: const EdgeInsets.only(top: 8),
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: const Color(0xFFD9D9D9),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                '选择数据源',
                style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
            const Divider(height: 1),
            Flexible(
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: available.length,
                itemBuilder: (_, index) {
                  final provider = available[index];
                  final colors = _colorsFor(provider.providerName.isNotEmpty
                      ? provider.providerName
                      : provider.category);
                  final icon = _iconFor(provider.providerName.isNotEmpty
                      ? provider.providerName
                      : provider.category);

                  return ListTile(
                    leading: Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: colors.$1,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(icon, size: 18, color: colors.$2),
                    ),
                    title: Text(provider.displayName),
                    subtitle: Text(
                      provider.description,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    trailing: const Icon(
                      Icons.add_circle_outline,
                      size: 20,
                      color: AppColors.accentGreen,
                    ),
                    onTap: () {
                      Navigator.of(sheetContext).pop();
                      _showConnectConfirmation(context, provider);
                    },
                  );
                },
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  void _showAddMcpDialog(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(sheetContext).viewInsets.bottom,
        ),
        child: _AddMcpSheet(
          onSubmit: (name, config) {
            Navigator.of(sheetContext).pop();
            context.read<ConnectionsBloc>().add(
                  CreateCustomMcpConnection(
                    displayName: name,
                    mcpServerUrl: config['url'] as String? ?? '',
                    mcpServerConfig: config,
                  ),
                );
          },
        ),
      ),
    );
  }

  String _formatRelativeTime(DateTime time) {
    final now = DateTime.now();
    final diff = now.difference(time);
    if (diff.inMinutes < 1) return '刚刚';
    if (diff.inHours < 1) return '${diff.inMinutes}分钟前';
    if (diff.inDays < 1) return '${diff.inHours}小时前';
    return '${diff.inDays}天前';
  }
}

// ──────── MCP Add Sheet (stateful) ────────

enum _McpTransport { sse, stdio, streamableHttp }

extension _McpTransportLabel on _McpTransport {
  String get label {
    switch (this) {
      case _McpTransport.sse:
        return 'SSE';
      case _McpTransport.stdio:
        return 'Stdio';
      case _McpTransport.streamableHttp:
        return 'Streamable HTTP';
    }
  }

  String get value {
    switch (this) {
      case _McpTransport.sse:
        return 'sse';
      case _McpTransport.stdio:
        return 'stdio';
      case _McpTransport.streamableHttp:
        return 'streamable-http';
    }
  }
}

class _AddMcpSheet extends StatefulWidget {
  final void Function(String name, Map<String, dynamic> config) onSubmit;

  const _AddMcpSheet({required this.onSubmit});

  @override
  State<_AddMcpSheet> createState() => _AddMcpSheetState();
}

class _AddMcpSheetState extends State<_AddMcpSheet> {
  _McpTransport _transport = _McpTransport.sse;
  final _nameController = TextEditingController();
  final _urlController = TextEditingController();
  final _commandController = TextEditingController();
  final _argsController = TextEditingController();
  final _headersKeyController = TextEditingController();
  final _headersValueController = TextEditingController();
  final _envKeyController = TextEditingController();
  final _envValueController = TextEditingController();

  final Map<String, String> _headers = {};
  final Map<String, String> _envVars = {};

  @override
  void dispose() {
    _nameController.dispose();
    _urlController.dispose();
    _commandController.dispose();
    _argsController.dispose();
    _headersKeyController.dispose();
    _headersValueController.dispose();
    _envKeyController.dispose();
    _envValueController.dispose();
    super.dispose();
  }

  bool get _isValid {
    if (_nameController.text.trim().isEmpty) return false;
    if (_transport == _McpTransport.stdio) {
      return _commandController.text.trim().isNotEmpty;
    }
    return _urlController.text.trim().isNotEmpty;
  }

  Map<String, dynamic> _buildConfig() {
    final config = <String, dynamic>{
      'transport': _transport.value,
    };

    if (_transport == _McpTransport.stdio) {
      config['command'] = _commandController.text.trim();
      final argsText = _argsController.text.trim();
      if (argsText.isNotEmpty) {
        config['args'] = argsText.split(RegExp(r'\s+'));
      }
    } else {
      config['url'] = _urlController.text.trim();
    }

    if (_headers.isNotEmpty) {
      config['headers'] = Map<String, String>.from(_headers);
    }
    if (_envVars.isNotEmpty) {
      config['env'] = Map<String, String>.from(_envVars);
    }

    return config;
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Handle bar
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: const Color(0xFFD9D9D9),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                '添加 MCP 服务',
                style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),

              // Service name
              _buildTextField(
                controller: _nameController,
                label: '服务名称',
                hint: '例如: GitHub, Notion, 自定义工具',
              ),
              const SizedBox(height: 16),

              // Transport type selector
              const Text(
                '传输协议',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 8),
              _buildTransportSelector(),
              const SizedBox(height: 16),

              // URL or Command fields based on transport
              if (_transport == _McpTransport.stdio) ...[
                _buildTextField(
                  controller: _commandController,
                  label: '命令',
                  hint: '例如: npx, uvx, node',
                ),
                const SizedBox(height: 12),
                _buildTextField(
                  controller: _argsController,
                  label: '参数 (空格分隔)',
                  hint: '例如: @modelcontextprotocol/server-github',
                ),
              ] else ...[
                _buildTextField(
                  controller: _urlController,
                  label: '服务器地址',
                  hint: _transport == _McpTransport.sse
                      ? 'https://mcp.example.com/sse'
                      : 'https://mcp.example.com/mcp',
                  keyboardType: TextInputType.url,
                ),
              ],

              const SizedBox(height: 16),

              // Environment variables section
              _buildKeyValueSection(
                title: '环境变量',
                entries: _envVars,
                keyController: _envKeyController,
                valueController: _envValueController,
                keyHint: 'GITHUB_TOKEN',
                valueHint: 'ghp_xxx...',
              ),
              const SizedBox(height: 12),

              // Headers section (for SSE / Streamable HTTP)
              if (_transport != _McpTransport.stdio) ...[
                _buildKeyValueSection(
                  title: 'HTTP Headers',
                  entries: _headers,
                  keyController: _headersKeyController,
                  valueController: _headersValueController,
                  keyHint: 'Authorization',
                  valueHint: 'Bearer xxx...',
                ),
                const SizedBox(height: 16),
              ],

              // Submit button
              const SizedBox(height: 8),
              FilledButton(
                onPressed: _isValid
                    ? () => widget.onSubmit(
                          _nameController.text.trim(),
                          _buildConfig(),
                        )
                    : null,
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.accentGreen,
                  disabledBackgroundColor: const Color(0xFFE5E4E1),
                  minimumSize: const Size.fromHeight(48),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  '添加服务',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTransportSelector() {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFF5F5F3),
        borderRadius: BorderRadius.circular(10),
      ),
      padding: const EdgeInsets.all(3),
      child: Row(
        children: _McpTransport.values.map((t) {
          final selected = _transport == t;
          return Expanded(
            child: GestureDetector(
              onTap: () => setState(() => _transport = t),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(vertical: 8),
                decoration: BoxDecoration(
                  color: selected ? Colors.white : Colors.transparent,
                  borderRadius: BorderRadius.circular(8),
                  boxShadow: selected
                      ? [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.06),
                            blurRadius: 4,
                            offset: const Offset(0, 1),
                          )
                        ]
                      : null,
                ),
                child: Text(
                  t.label,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                    color: selected
                        ? AppColors.textPrimary
                        : AppColors.textSecondary,
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    TextInputType keyboardType = TextInputType.text,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          keyboardType: keyboardType,
          onChanged: (_) => setState(() {}),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: const TextStyle(
              fontSize: 14,
              color: AppColors.textTertiary,
            ),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            filled: true,
            fillColor: const Color(0xFFF5F5F3),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide.none,
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide.none,
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide:
                  const BorderSide(color: AppColors.accentGreen, width: 1.5),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildKeyValueSection({
    required String title,
    required Map<String, String> entries,
    required TextEditingController keyController,
    required TextEditingController valueController,
    required String keyHint,
    required String valueHint,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              title,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: AppColors.textSecondary,
              ),
            ),
            const Spacer(),
            if (entries.isEmpty)
              Text(
                '可选',
                style: TextStyle(
                  fontSize: 11,
                  color: AppColors.textTertiary.withValues(alpha: 0.7),
                ),
              ),
          ],
        ),
        const SizedBox(height: 6),

        // Existing entries
        for (final entry in entries.entries)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F5F3),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Text(
                    entry.key,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Text('=',
                      style: TextStyle(color: AppColors.textTertiary)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      entry.value.length > 20
                          ? '${entry.value.substring(0, 8)}...${entry.value.substring(entry.value.length - 4)}'
                          : entry.value,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ),
                  GestureDetector(
                    onTap: () => setState(() => entries.remove(entry.key)),
                    child: const Icon(Icons.close,
                        size: 16, color: AppColors.textTertiary),
                  ),
                ],
              ),
            ),
          ),

        // Add new entry row
        Row(
          children: [
            Expanded(
              flex: 2,
              child: TextField(
                controller: keyController,
                style: const TextStyle(fontSize: 13),
                decoration: InputDecoration(
                  hintText: keyHint,
                  hintStyle: const TextStyle(
                      fontSize: 12, color: AppColors.textTertiary),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  isDense: true,
                  filled: true,
                  fillColor: const Color(0xFFF5F5F3),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              flex: 3,
              child: TextField(
                controller: valueController,
                style: const TextStyle(fontSize: 13),
                obscureText: title == '环境变量',
                decoration: InputDecoration(
                  hintText: valueHint,
                  hintStyle: const TextStyle(
                      fontSize: 12, color: AppColors.textTertiary),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  isDense: true,
                  filled: true,
                  fillColor: const Color(0xFFF5F5F3),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            GestureDetector(
              onTap: () {
                final k = keyController.text.trim();
                final v = valueController.text.trim();
                if (k.isNotEmpty && v.isNotEmpty) {
                  setState(() {
                    entries[k] = v;
                    keyController.clear();
                    valueController.clear();
                  });
                }
              },
              child: Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: AppColors.accentGreenLight,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.add,
                    size: 18, color: AppColors.accentGreen),
              ),
            ),
          ],
        ),
      ],
    );
  }
}
