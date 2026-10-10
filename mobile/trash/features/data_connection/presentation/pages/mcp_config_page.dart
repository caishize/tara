import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/connector_metadata_model.dart';
import '../../domain/entities/connector_metadata.dart';
import '../bloc/connection_bloc.dart';
import '../bloc/connection_event.dart';
import '../bloc/connection_state.dart' as bloc;

/// Page for configuring MCP (Model Context Protocol) connections
class MCPConfigPage extends StatefulWidget {
  final String connectorId;
  final String? connectionId;

  const MCPConfigPage({
    required this.connectorId,
    this.connectionId,
    super.key,
  });

  @override
  State<MCPConfigPage> createState() => _MCPConfigPageState();
}

class _MCPConfigPageState extends State<MCPConfigPage> {
  final _formKey = GlobalKey<FormState>();
  final _commandController = TextEditingController();
  final _envController = TextEditingController();

  bool _isAdvancedMode = false;
  ConnectorMetadata? _connector;

  @override
  void initState() {
    super.initState();
    _loadConnectorInfo();
  }

  void _loadConnectorInfo() {
    final state = context.read<ConnectionBloc>().state;
    if (state is bloc.ConnectionLoaded) {
      final connector = state.connectors.firstWhere(
        (c) => c.id == widget.connectorId,
        orElse: () => ConnectorMetadataModel(
          id: widget.connectorId,
          name: widget.connectorId,
          displayName: 'MCP Server',
          displayNameZh: 'MCP 服务器',
          description: '',
          descriptionZh: '',
          icon: 'terminal',
          category: DataCategory.productivity,
          authType: AuthType.mcp,
          capabilities: const ConnectorCapabilities(),
          requiredScopes: const [],
          optionalScopes: const [],
          dataRetentionDays: 30,
          isAvailable: true,
          regions: const ['GLOBAL'],
          dataUsageDescription: '',
          dataUsageDescriptionZh: '',
        ),
      );
      setState(() {
        _connector = connector;
      });
    }
  }

  @override
  void dispose() {
    _commandController.dispose();
    _envController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(_connector?.displayNameZh ?? 'MCP \u914d\u7f6e'),
        actions: [
          TextButton(
            onPressed: _isFormValid() ? _saveConfig : null,
            child: const Text('\u4fdd\u5b58'),
          ),
        ],
      ),
      body: BlocListener<ConnectionBloc, bloc.DataConnectionState>(
        listener: (context, state) {
          if (state is bloc.ConnectionOperationSuccess) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: Colors.green,
              ),
            );
            context.pop();
          } else if (state is bloc.ConnectionError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: Colors.red,
              ),
            );
          }
        },
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Info Card
                _buildInfoCard(theme),
                const SizedBox(height: 24),

                // Basic Configuration
                _buildSectionHeader(theme, 'MCP \u670d\u52a1\u5668\u914d\u7f6e'),
                const SizedBox(height: 12),
                _buildCommandField(theme),
                const SizedBox(height: 24),

                // Advanced Settings Toggle
                _buildAdvancedToggle(theme),

                // Advanced Settings
                if (_isAdvancedMode) ...[
                  const SizedBox(height: 16),
                  _buildEnvVarsField(theme),
                ],

                const SizedBox(height: 32),

                // Help Section
                _buildHelpSection(theme),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildInfoCard(ThemeData theme) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: AppColors.primary.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                _getConnectorIcon(),
                color: AppColors.primary,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _connector?.displayNameZh ?? 'MCP \u670d\u52a1\u5668',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _connector?.descriptionZh ?? 'MCP (Model Context Protocol) \u8fde\u63a5',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionHeader(ThemeData theme, String title) {
    return Text(
      title,
      style: theme.textTheme.titleSmall?.copyWith(
        fontWeight: FontWeight.w600,
        color: AppColors.textSecondary,
      ),
    );
  }

  Widget _buildCommandField(ThemeData theme) {
    final isGeneric = widget.connectorId == 'generic_mcp';

    return TextFormField(
      controller: _commandController,
      decoration: InputDecoration(
        labelText: isGeneric ? '\u670d\u52a1\u5668\u542f\u52a8\u547d\u4ee4 *' : '\u670d\u52a1\u5668\u542f\u52a8\u547d\u4ee4',
        hintText: 'npx @modelcontextprotocol/server-xxx',
        helperText: isGeneric
            ? '\u8bf7\u8f93\u5165 MCP \u670d\u52a1\u5668\u7684\u542f\u52a8\u547d\u4ee4'
            : '\u7559\u7a7a\u4f7f\u7528\u9ed8\u8ba4\u547d\u4ee4',
        border: const OutlineInputBorder(),
        prefixIcon: const Icon(Icons.terminal),
      ),
      validator: isGeneric
          ? (value) {
              if (value == null || value.trim().isEmpty) {
                return '\u8bf7\u8f93\u5165\u670d\u52a1\u5668\u542f\u52a8\u547d\u4ee4';
              }
              return null;
            }
          : null,
    );
  }

  Widget _buildAdvancedToggle(ThemeData theme) {
    return InkWell(
      onTap: () {
        setState(() {
          _isAdvancedMode = !_isAdvancedMode;
        });
      },
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            Icon(
              _isAdvancedMode
                  ? Icons.keyboard_arrow_up
                  : Icons.keyboard_arrow_down,
              color: AppColors.primary,
            ),
            const SizedBox(width: 8),
            Text(
              '\u9ad8\u7ea7\u8bbe\u7f6e',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: AppColors.primary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEnvVarsField(ThemeData theme) {
    return TextFormField(
      controller: _envController,
      decoration: const InputDecoration(
        labelText: '\u73af\u5883\u53d8\u91cf',
        hintText: 'API_KEY=xxx\nOTHER_VAR=yyy',
        helperText: '\u6bcf\u884c\u4e00\u4e2a\u73af\u5883\u53d8\u91cf\uff0c\u683c\u5f0f: KEY=VALUE',
        border: OutlineInputBorder(),
        prefixIcon: Icon(Icons.settings),
      ),
      maxLines: 4,
    );
  }

  Widget _buildHelpSection(ThemeData theme) {
    return Card(
      color: Colors.blue.shade50,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.info_outline, color: Colors.blue.shade700, size: 20),
                const SizedBox(width: 8),
                Text(
                  '\u4ec0\u4e48\u662f MCP\uff1f',
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: Colors.blue.shade700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'MCP (Model Context Protocol) \u662f\u4e00\u79cd\u5f00\u653e\u534f\u8bae\uff0c\u5141\u8bb8 AI \u52a9\u624b\u8fde\u63a5\u5916\u90e8\u5de5\u5177\u548c\u6570\u636e\u6e90\u3002'
              '\n\n\u901a\u8fc7 MCP\uff0c\u60a8\u53ef\u4ee5\uff1a'
              '\n\u2022 \u8bbf\u95ee\u672c\u5730\u6587\u4ef6\u7cfb\u7edf'
              '\n\u2022 \u83b7\u53d6\u7f51\u9875\u5185\u5bb9'
              '\n\u2022 \u8c03\u7528\u81ea\u5b9a\u4e49\u5de5\u5177'
              '\n\u2022 \u96c6\u6210\u7b2c\u4e09\u65b9\u670d\u52a1',
              style: theme.textTheme.bodySmall?.copyWith(
                color: Colors.blue.shade700,
              ),
            ),
            const SizedBox(height: 12),
            TextButton.icon(
              onPressed: () {
                // TODO: Open MCP documentation
              },
              icon: const Icon(Icons.open_in_new, size: 16),
              label: const Text('\u4e86\u89e3\u66f4\u591a'),
              style: TextButton.styleFrom(
                padding: EdgeInsets.zero,
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ),
          ],
        ),
      ),
    );
  }

  IconData _getConnectorIcon() {
    switch (widget.connectorId) {
      case 'filesystem_mcp':
        return Icons.folder;
      case 'fetch_mcp':
        return Icons.language;
      case 'memory_mcp':
        return Icons.psychology;
      default:
        return Icons.terminal;
    }
  }

  bool _isFormValid() {
    final isGeneric = widget.connectorId == 'generic_mcp';
    if (isGeneric) {
      return _commandController.text.trim().isNotEmpty;
    }
    return true; // Non-generic MCP connectors can use default command
  }

  void _saveConfig() {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    // Build MCP configuration
    final config = <String, dynamic>{};

    if (_commandController.text.trim().isNotEmpty) {
      config['command'] = _commandController.text.trim().split(' ');
    }

    if (_envController.text.trim().isNotEmpty) {
      final env = <String, String>{};
      for (final line in _envController.text.trim().split('\n')) {
        final parts = line.split('=');
        if (parts.length >= 2) {
          env[parts[0].trim()] = parts.sublist(1).join('=').trim();
        }
      }
      if (env.isNotEmpty) {
        config['env'] = env;
      }
    }

    // Complete connection with config as JSON
    final configJson = jsonEncode(config);

    if (widget.connectionId != null) {
      // Complete existing connection
      context.read<ConnectionBloc>().add(CompleteConnection(
            connectionId: widget.connectionId!,
            code: configJson,
          ));
    } else {
      // Initiate new connection first
      context.read<ConnectionBloc>().add(InitiateConnection(
            connectorId: widget.connectorId,
            scopes: [],
          ));
      // TODO: Handle the two-step flow properly
    }
  }
}
