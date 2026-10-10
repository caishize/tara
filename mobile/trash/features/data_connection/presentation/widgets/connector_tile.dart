import 'package:flutter/material.dart';

import '../../domain/entities/connector_metadata.dart';
import '../../../../app/theme/app_colors.dart';

/// Tile for displaying a connector option
class ConnectorTile extends StatelessWidget {
  final ConnectorMetadata connector;
  final bool isConnected;
  final VoidCallback? onTap;

  const ConnectorTile({
    super.key,
    required this.connector,
    this.isConnected = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      leading: _buildIcon(context),
      title: Text(
        connector.displayNameZh,
        style: theme.textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w500,
        ),
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 4),
          Text(
            connector.descriptionZh,
            style: theme.textTheme.bodySmall?.copyWith(
              color: AppColors.textSecondary,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 4,
            children: connector.capabilities.toDisplayList().take(3).map((cap) {
              return _buildCapabilityChip(context, cap);
            }).toList(),
          ),
        ],
      ),
      trailing: isConnected
          ? const Icon(Icons.check_circle, color: Colors.green)
          : connector.isAvailable
              ? const Icon(Icons.chevron_right, color: AppColors.textSecondary)
              : Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.grey.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    '即将推出',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey,
                    ),
                  ),
                ),
      onTap: isConnected ? null : onTap,
    );
  }

  Widget _buildIcon(BuildContext context) {
    IconData iconData;
    Color color;

    switch (connector.icon) {
      case 'google':
        iconData = Icons.g_mobiledata;
        color = Colors.red;
        break;
      case 'microsoft':
        iconData = Icons.window;
        color = Colors.blue;
        break;
      case 'apple':
        iconData = Icons.apple;
        color = Colors.grey;
        break;
      case 'calendar_today':
        iconData = Icons.calendar_today;
        color = AppColors.primary;
        break;
      case 'email':
        iconData = Icons.email;
        color = Colors.orange;
        break;
      case 'shopping_cart':
        iconData = Icons.shopping_cart;
        color = Colors.orange;
        break;
      case 'shopping_bag':
        iconData = Icons.shopping_bag;
        color = Colors.deepOrange;
        break;
      case 'restaurant':
        iconData = Icons.restaurant;
        color = Colors.amber;
        break;
      case 'fastfood':
        iconData = Icons.fastfood;
        color = Colors.blue;
        break;
      case 'account_balance_wallet':
        iconData = Icons.account_balance_wallet;
        color = Colors.blue;
        break;
      case 'chat':
        iconData = Icons.chat;
        color = Colors.green;
        break;
      case 'flight':
        iconData = Icons.flight;
        color = Colors.blue;
        break;
      case 'local_taxi':
        iconData = Icons.local_taxi;
        color = Colors.orange;
        break;
      case 'terminal':
        iconData = Icons.terminal;
        color = Colors.purple;
        break;
      case 'folder':
        iconData = Icons.folder;
        color = Colors.amber;
        break;
      case 'language':
        iconData = Icons.language;
        color = Colors.blue;
        break;
      case 'psychology':
        iconData = Icons.psychology;
        color = Colors.purple;
        break;
      default:
        iconData = _getCategoryIcon(connector.category);
        color = AppColors.primary;
    }

    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        color: (isConnected ? Colors.green : color).withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(
        iconData,
        color: isConnected ? Colors.green : color,
        size: 24,
      ),
    );
  }

  IconData _getCategoryIcon(DataCategory category) {
    switch (category) {
      case DataCategory.calendar:
        return Icons.calendar_today;
      case DataCategory.email:
        return Icons.email;
      case DataCategory.ecommerce:
        return Icons.shopping_cart;
      case DataCategory.foodDelivery:
        return Icons.restaurant;
      case DataCategory.social:
        return Icons.people;
      case DataCategory.health:
        return Icons.favorite;
      case DataCategory.finance:
        return Icons.account_balance;
      case DataCategory.location:
        return Icons.location_on;
      case DataCategory.travel:
        return Icons.flight;
      case DataCategory.productivity:
        return Icons.construction;
      case DataCategory.other:
        return Icons.extension;
    }
  }

  Widget _buildCapabilityChip(BuildContext context, String capability) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.primary.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        capability,
        style: const TextStyle(
          fontSize: 10,
          color: AppColors.primary,
        ),
      ),
    );
  }
}
