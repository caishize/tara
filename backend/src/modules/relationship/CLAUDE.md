# Relationship

## Purpose
Favor tracking, care suggestions, and relationship health scoring — helps users maintain social reciprocity and nurture important relationships.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models, .schemas, ..member.interface
- **Forbidden imports**: ai_engine.*, api.*

## Key Files
| File | Purpose |
|------|---------|
| interface.py | Abstract contracts: IFavorService, ICareService |
| favor_service.py | Favor recording, balance tracking |
| care_service.py | Care suggestions and relationship health |
| thermometer.py | Relationship warmth/health scoring |
| models.py | FavorRecord, SocialEvent SQLAlchemy models |
| schemas.py | Pydantic request/response schemas |
| algorithms/relationship_decay.py | Time-based relationship decay algorithm |

## Module Conventions
- Favor balance is directional: `gave` vs `received`
- Health scores combine favor balance + interaction recency + decay
- Care suggestions are rule-based (no LLM), generated from health scores
