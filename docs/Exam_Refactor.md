## Exam refactor

| Concept | Category | Main files modified | How to test it |
|---|---|---|---|
| Compensation path for a distributed operation | B | `trip_service/main.py`, `trip_service/clients.py` | `docker compose run --rm tools python scripts/demo_compensation.py` |

### AI assistance disclosure
Claude was used for generating the demo script with scenerios needed. The implementation logic and tracking which resources were reserved, calling cancel endpoints in reverse order, and handling compensation failures independently was written by me.