import 'package:flutter/material.dart';
import '../../app/theme/app_colors.dart';

/// An avatar widget that displays initials or an image.
class AvatarWithInitials extends StatelessWidget {
  final String? name;
  final String? imageUrl;
  final double size;
  final Color? backgroundColor;
  final Color? textColor;
  final double? fontSize;
  final IconData? fallbackIcon;

  const AvatarWithInitials({
    super.key,
    this.name,
    this.imageUrl,
    this.size = 48,
    this.backgroundColor,
    this.textColor,
    this.fontSize,
    this.fallbackIcon,
  });

  String get _initials {
    if (name == null || name!.isEmpty) return '';
    final parts = name!.trim().split(' ');
    if (parts.length >= 2) {
      return '${parts.first[0]}${parts.last[0]}'.toUpperCase();
    }
    return name!.substring(0, name!.length >= 2 ? 2 : 1).toUpperCase();
  }

  Color get _backgroundColor {
    if (backgroundColor != null) return backgroundColor!;
    if (name == null || name!.isEmpty) return AppColors.chipBackground;

    // Generate a consistent color based on name
    final hash = name!.hashCode;
    final colors = [
      AppColors.badgeGreen,
      AppColors.badgeOrange,
      AppColors.badgePink,
      AppColors.badgePurple,
      AppColors.badgeBlue,
      AppColors.chipBackground,
    ];
    return colors[hash.abs() % colors.length];
  }

  Color get _textColor {
    if (textColor != null) return textColor!;
    return AppColors.primary;
  }

  @override
  Widget build(BuildContext context) {
    if (imageUrl != null && imageUrl!.isNotEmpty) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(size / 2),
        child: Image.network(
          imageUrl!,
          width: size,
          height: size,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) => _buildInitials(),
        ),
      );
    }
    return _buildInitials();
  }

  Widget _buildInitials() {
    final initials = _initials;

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: _backgroundColor,
        borderRadius: BorderRadius.circular(size / 2),
      ),
      alignment: Alignment.center,
      child: initials.isNotEmpty
          ? Text(
              initials,
              style: TextStyle(
                fontSize: fontSize ?? size * 0.35,
                fontWeight: FontWeight.w600,
                color: _textColor,
              ),
            )
          : Icon(
              fallbackIcon ?? Icons.person,
              size: size * 0.5,
              color: _textColor,
            ),
    );
  }
}

/// A square avatar with rounded corners for icon shortcuts.
class IconAvatar extends StatelessWidget {
  final IconData icon;
  final double size;
  final Color? backgroundColor;
  final Color? iconColor;
  final double? borderRadius;
  final String? badge;
  final Color? badgeColor;

  const IconAvatar({
    super.key,
    required this.icon,
    this.size = 56,
    this.backgroundColor,
    this.iconColor,
    this.borderRadius,
    this.badge,
    this.badgeColor,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            color: backgroundColor ?? AppColors.chipBackground,
            borderRadius: BorderRadius.circular(borderRadius ?? 16),
          ),
          child: Icon(
            icon,
            size: size * 0.45,
            color: iconColor ?? AppColors.primary,
          ),
        ),
        if (badge != null)
          Positioned(
            top: -4,
            right: -4,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: badgeColor ?? AppColors.error,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                badge!,
                style: const TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// A group of overlapping avatars.
class AvatarGroup extends StatelessWidget {
  final List<AvatarData> avatars;
  final double size;
  final int maxDisplay;
  final double overlap;

  const AvatarGroup({
    super.key,
    required this.avatars,
    this.size = 32,
    this.maxDisplay = 4,
    this.overlap = 0.3,
  });

  @override
  Widget build(BuildContext context) {
    final displayCount = avatars.length > maxDisplay ? maxDisplay : avatars.length;
    final extra = avatars.length - maxDisplay;

    return SizedBox(
      width: size + (displayCount - 1) * size * (1 - overlap) + (extra > 0 ? size * (1 - overlap) : 0),
      height: size,
      child: Stack(
        children: [
          for (int i = 0; i < displayCount; i++)
            Positioned(
              left: i * size * (1 - overlap),
              child: Container(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: Colors.white,
                    width: 2,
                  ),
                ),
                child: AvatarWithInitials(
                  name: avatars[i].name,
                  imageUrl: avatars[i].imageUrl,
                  size: size - 4,
                  backgroundColor: avatars[i].backgroundColor,
                ),
              ),
            ),
          if (extra > 0)
            Positioned(
              left: displayCount * size * (1 - overlap),
              child: Container(
                width: size,
                height: size,
                decoration: BoxDecoration(
                  color: AppColors.textTertiary,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: Colors.white,
                    width: 2,
                  ),
                ),
                alignment: Alignment.center,
                child: Text(
                  '+$extra',
                  style: TextStyle(
                    fontSize: size * 0.3,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Data class for AvatarGroup.
class AvatarData {
  final String? name;
  final String? imageUrl;
  final Color? backgroundColor;

  const AvatarData({
    this.name,
    this.imageUrl,
    this.backgroundColor,
  });
}
