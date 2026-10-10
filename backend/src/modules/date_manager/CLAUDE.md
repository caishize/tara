# Date Manager

## Purpose
Important date tracking — manages birthdays, anniversaries, holidays (including lunar calendar), smart reminder strategies, and holiday preparation workflows.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models, ..member.interface
- **Forbidden imports**: ai_engine.*, api.*, other module services

## Key Files
| File | Purpose |
|------|---------|
| date_service.py | Important date CRUD with recurrence handling |
| date_repository.py | Date persistence and queries |
| reminder_service.py | Smart reminder scheduling (configurable lead days) |
| reminder_repository.py | Reminder persistence |
| holiday_preparation_service.py | Holiday prep workflow (gifts, travel, greetings) |
| holiday_repository.py | Holiday data persistence |
| lunar_provider.py | Lunar calendar date conversion |
| calendar_adapter.py | External calendar integration adapter |
| event_reminder.py | Reminder delivery trigger |
| enums.py | DateType, RecurrenceType, ReminderStrategy enums |
| tasks.py | Celery tasks: holiday prep (daily 06:00), reminder dispatch (30s) |

## Module Conventions
- Lunar dates stored as `lunar_year/month/day` alongside Gregorian `date_value`
- `preparation_lead_days` column allows per-type defaults (birthday=14d, festival=30d)
- All DateTimes use `DateTime(timezone=True)` and `utc_now()`
- Templates in `templates/` directory for reminder message formatting
