import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/user.dart';
import '../bloc/auth_bloc.dart';

/// Edit profile page matching the "编辑资料" prototype
class EditProfilePage extends StatefulWidget {
  const EditProfilePage({super.key});

  @override
  State<EditProfilePage> createState() => _EditProfilePageState();
}

class _EditProfilePageState extends State<EditProfilePage> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _nicknameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _emailController = TextEditingController();
  String _selectedTimezone = 'Asia/Shanghai (UTC+8)';

  static const _timezoneOptions = [
    'Asia/Shanghai (UTC+8)',
    'Asia/Tokyo (UTC+9)',
    'Asia/Hong_Kong (UTC+8)',
    'Asia/Singapore (UTC+8)',
    'America/New_York (UTC-5)',
    'America/Los_Angeles (UTC-8)',
    'Europe/London (UTC+0)',
    'Europe/Paris (UTC+1)',
    'Australia/Sydney (UTC+11)',
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // Populate from current state immediately
      final currentState = context.read<AuthBloc>().state;
      if (currentState is AuthAuthenticated) {
        _populateFields(currentState.user);
      }
      // Then fetch fresh data from API (will update if different)
      context.read<AuthBloc>().add(const AuthFetchProfileRequested());
    });
  }

  void _populateFields(User user) {
    _usernameController.text = user.username;
    _nicknameController.text = user.nickname ?? '';
    _phoneController.text = user.phone ?? '';
    _emailController.text = user.email ?? '';
    if (user.timezone != null && user.timezone!.isNotEmpty) {
      setState(() => _selectedTimezone = user.timezone!);
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _nicknameController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    super.dispose();
  }

  void _handleSubmit() {
    if (_formKey.currentState?.validate() ?? false) {
      final authBloc = context.read<AuthBloc>();
      final currentState = authBloc.state;
      if (currentState is AuthAuthenticated) {
        final user = currentState.user;
        final newUsername = _usernameController.text.trim();
        final newNickname = _nicknameController.text.trim();
        final newPhone = _phoneController.text.trim();
        final newEmail = _emailController.text.trim();

        // null = don't change, value = update (empty string = clear)
        String? usernameToSend;
        String? nicknameToSend;
        String? phoneToSend;
        String? emailToSend;
        String? timezoneToSend;
        bool hasChanges = false;

        if (newUsername != user.username) {
          usernameToSend = newUsername;
          hasChanges = true;
        }
        if (newNickname != (user.nickname ?? '')) {
          nicknameToSend = newNickname; // empty string = clear nickname
          hasChanges = true;
        }
        if (newPhone != (user.phone ?? '')) {
          phoneToSend = newPhone; // empty string = clear phone
          hasChanges = true;
        }
        if (newEmail != (user.email ?? '')) {
          emailToSend = newEmail; // empty string = clear email
          hasChanges = true;
        }
        if (_selectedTimezone != (user.timezone ?? 'Asia/Shanghai (UTC+8)')) {
          timezoneToSend = _selectedTimezone;
          hasChanges = true;
        }

        if (hasChanges) {
          authBloc.add(AuthUpdateProfileRequested(
            username: usernameToSend,
            nickname: nicknameToSend,
            phone: phoneToSend,
            email: emailToSend,
            timezone: timezoneToSend,
          ));
        } else {
          context.pop();
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<AuthBloc, AuthState>(
      listener: (context, state) {
        if (state is AuthAuthenticated) {
          _populateFields(state.user);
        }
        if (state is AuthError) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(state.message),
              backgroundColor: AppColors.error,
            ),
          );
        } else if (state is AuthOperationSuccess) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(state.message),
              backgroundColor: AppColors.success,
            ),
          );
          context.pop();
        }
      },
      builder: (context, state) {
        final isLoading = state is AuthOperationInProgress;

        String displayName = '';
        if (state is AuthAuthenticated) {
          displayName = state.user.displayName;
        } else if (state is AuthOperationInProgress) {
          displayName = state.user.displayName;
        }
        final firstChar = displayName.isNotEmpty ? displayName[0] : '?';

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
                '编辑资料',
                style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              actions: [
                TextButton(
                  onPressed: isLoading ? null : _handleSubmit,
                  child: isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text(
                          '保存',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: AppColors.accentGreen,
                          ),
                        ),
                ),
              ],
            ),
            body: SafeArea(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Avatar section
                      _buildAvatarSection(firstChar),
                      const SizedBox(height: 24),

                      // Form fields
                      _buildUsernameField(),
                      const SizedBox(height: 20),
                      _buildNicknameField(),
                      const SizedBox(height: 20),
                      _buildPhoneField(),
                      const SizedBox(height: 20),
                      _buildEmailField(),
                      const SizedBox(height: 20),
                      _buildTimezoneField(),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
    );
  }

  Widget _buildAvatarSection(String firstChar) {
    return Center(
      child: Column(
        children: [
          GestureDetector(
            onTap: () {
              // TODO: Implement avatar picker
            },
            child: SizedBox(
              width: 80,
              height: 80,
              child: Stack(
                children: [
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      color: AppColors.accentGreen,
                      borderRadius: BorderRadius.circular(40),
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      firstChar,
                      style: const TextStyle(
                        fontSize: 36,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  Positioned(
                    right: 0,
                    bottom: 0,
                    child: Container(
                      width: 28,
                      height: 28,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(14),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.1),
                            blurRadius: 4,
                            offset: const Offset(0, 1),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.camera_alt_outlined,
                        size: 16,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            '点击更换头像',
            style: TextStyle(
              fontSize: 13,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildUsernameField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Text(
              '用户名',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: AppColors.textPrimary,
              ),
            ),
            Text(
              ' *',
              style: TextStyle(color: AppColors.error),
            ),
          ],
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: _usernameController,
          validator: (value) {
            if (value == null || value.trim().isEmpty) {
              return '用户名不能为空';
            }
            if (value.trim().length < 2) {
              return '用户名至少需要2个字符';
            }
            return null;
          },
          decoration: _inputDecoration('请输入用户名'),
        ),
      ],
    );
  }

  Widget _buildNicknameField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '昵称',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: _nicknameController,
          decoration: _inputDecoration('请输入昵称'),
        ),
        const SizedBox(height: 8),
        const Text(
          '昵称将在应用中显示，若不设置则显示用户名',
          style: TextStyle(
            fontSize: 12,
            color: AppColors.textTertiary,
          ),
        ),
      ],
    );
  }

  Widget _buildPhoneField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '手机号码',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: _phoneController,
          keyboardType: TextInputType.phone,
          decoration: _inputDecoration('请输入手机号码'),
        ),
      ],
    );
  }

  Widget _buildEmailField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '邮箱地址',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: _emailController,
          keyboardType: TextInputType.emailAddress,
          validator: (value) {
            if (value != null && value.trim().isNotEmpty) {
              final emailRegex = RegExp(r'^[\w\-.]+@[\w\-.]+\.\w+$');
              if (!emailRegex.hasMatch(value.trim())) {
                return '请输入有效的邮箱地址';
              }
            }
            return null;
          },
          decoration: _inputDecoration('请输入邮箱地址'),
        ),
      ],
    );
  }

  Widget _buildTimezoneField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '时区',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        GestureDetector(
          onTap: _showTimezoneSelector,
          child: Container(
            height: 44,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.divider),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    _selectedTimezone,
                    style: const TextStyle(
                      fontSize: 15,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
                const Icon(
                  Icons.keyboard_arrow_down,
                  color: AppColors.textTertiary,
                  size: 20,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  InputDecoration _inputDecoration(String hint) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: AppColors.textTertiary),
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.divider),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.divider),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.accentGreen, width: 2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.error),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
    );
  }

  void _showTimezoneSelector() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                '选择时区',
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
                itemCount: _timezoneOptions.length,
                itemBuilder: (context, index) {
                  final tz = _timezoneOptions[index];
                  final isSelected = tz == _selectedTimezone;
                  return ListTile(
                    title: Text(
                      tz,
                      style: TextStyle(
                        fontSize: 15,
                        color: isSelected
                            ? AppColors.accentGreen
                            : AppColors.textPrimary,
                        fontWeight:
                            isSelected ? FontWeight.w600 : FontWeight.normal,
                      ),
                    ),
                    trailing: isSelected
                        ? const Icon(Icons.check,
                            color: AppColors.accentGreen, size: 20)
                        : null,
                    onTap: () {
                      setState(() => _selectedTimezone = tz);
                      Navigator.pop(ctx);
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
