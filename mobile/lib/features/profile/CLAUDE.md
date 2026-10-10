# Profile Module

## Purpose
User profile tab: stats dashboard, family member connections, AI memory browser, smart service management (toggle/trigger), app settings, insight settings, work reports, privacy/security, and data backup.

## Layer Rules
- **Layer**: feature (`features/profile/`)
- **Allowed imports**: `core/`, `shared/`, `domain/` and `data/` within this feature
- **Forbidden imports**: other `features/` modules

## Key Files
| File | Purpose |
|------|---------|
| `presentation/bloc/profile_bloc.dart` | Profile + stats + smart services (events/state in same file) |
| `presentation/bloc/connections_bloc.dart` | Family member connections CRUD |
| `presentation/bloc/memory_browser_bloc.dart` | AI memory search and browsing |
| `presentation/bloc/settings_bloc.dart` | App + insight settings management |
| `presentation/bloc/work_report_bloc.dart` | Secretary work reports |
| `presentation/pages/profile_page.dart` | Main profile tab with cards |
| `presentation/pages/smart_services_page.dart` | Toggle/trigger background AI services |
| `data/datasources/profile_remote_datasource.dart` | Profile API calls (stats, services) |
| `data/datasources/connections_remote_datasource.dart` | Family connections API |
| `domain/entities/smart_service.dart` | SmartService entity with enabled/schedule fields |
| `domain/entities/user_stats.dart` | Usage statistics entity |

## Module Conventions
- ProfileBloc combines events + state in a single file (unlike other modules)
- 8 BLoCs total: profile, connections, memory_browser, settings, activity, insight_history, service_detail, work_report
- Smart services use toggle (enable/disable) + trigger (manual run) pattern
- Widget cards compose the profile page: `profile_header_card`, `stats_card`, `smart_services_section`, `data_connections_card`, `secretary_report_card`
