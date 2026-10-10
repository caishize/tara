# Member

## Purpose
Family member management — user/family CRUD, person profiles (non-user contacts), device tokens, trust scoring, professional relations, and profile enrichment from conversations.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models, ..memory.interface
- **Forbidden imports**: ai_engine.*, api.*, other module services

## Key Files
| File | Purpose |
|------|---------|
| member_service.py | Family member CRUD and family-level operations |
| person_service.py | Non-user person profiles (contacts, relatives) |
| trust_service.py | Trust scoring and verification |
| trust_repair.py | Trust recovery after violations |
| connection_service.py | Social connections between members |
| professional_relation_service.py | Work relationships (colleagues, managers) |
| device_token_service.py | Push notification device token management |
| context_service.py | Family context assembly for LLM prompts |
| profile_enrichment.py | Auto-enriches profiles from conversation data |
| models/ | SQLAlchemy models: FamilyMember, Person, DeviceToken |
| repositories/ | Data access layer |

## Module Conventions
- Family isolation enforced: always `verify_member_belongs_to_family()` before access
- Profiles enriched incrementally from conversations (not batch)
- Trust levels gate sensitive operations (spending, travel booking)
- `current_work_helper.py` provides quick member context lookups
