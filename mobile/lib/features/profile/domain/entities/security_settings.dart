import 'package:equatable/equatable.dart';

class SecuritySettings extends Equatable {
  final bool biometricEnabled;
  final bool pinEnabled;
  final bool hasPinCode;

  const SecuritySettings({
    this.biometricEnabled = false,
    this.pinEnabled = false,
    this.hasPinCode = false,
  });

  SecuritySettings copyWith({
    bool? biometricEnabled,
    bool? pinEnabled,
    bool? hasPinCode,
  }) =>
      SecuritySettings(
        biometricEnabled: biometricEnabled ?? this.biometricEnabled,
        pinEnabled: pinEnabled ?? this.pinEnabled,
        hasPinCode: hasPinCode ?? this.hasPinCode,
      );

  @override
  List<Object?> get props => [biometricEnabled, pinEnabled, hasPinCode];
}
