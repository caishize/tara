import 'package:equatable/equatable.dart';

class BackupInfo extends Equatable {
  final DateTime? lastBackupTime;
  final bool autoBackupEnabled;
  final int? backupSizeBytes;

  const BackupInfo({
    this.lastBackupTime,
    this.autoBackupEnabled = false,
    this.backupSizeBytes,
  });

  String get lastBackupText {
    if (lastBackupTime == null) return '从未备份';

    final now = DateTime.now();
    final diff = now.difference(lastBackupTime!);

    if (diff.inMinutes < 1) return '刚刚';
    if (diff.inHours < 1) return '${diff.inMinutes}分钟前';
    if (diff.inDays < 1) return '${diff.inHours}小时前';
    if (diff.inDays < 7) return '${diff.inDays}天前';

    return '${lastBackupTime!.year}-${lastBackupTime!.month.toString().padLeft(2, '0')}-${lastBackupTime!.day.toString().padLeft(2, '0')}';
  }

  String get backupSizeText {
    if (backupSizeBytes == null) return '未知';
    if (backupSizeBytes! < 1024) return '$backupSizeBytes B';
    if (backupSizeBytes! < 1024 * 1024) {
      return '${(backupSizeBytes! / 1024).toStringAsFixed(1)} KB';
    }
    return '${(backupSizeBytes! / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  BackupInfo copyWith({
    DateTime? lastBackupTime,
    bool? autoBackupEnabled,
    int? backupSizeBytes,
  }) =>
      BackupInfo(
        lastBackupTime: lastBackupTime ?? this.lastBackupTime,
        autoBackupEnabled: autoBackupEnabled ?? this.autoBackupEnabled,
        backupSizeBytes: backupSizeBytes ?? this.backupSizeBytes,
      );

  @override
  List<Object?> get props => [lastBackupTime, autoBackupEnabled, backupSizeBytes];
}
