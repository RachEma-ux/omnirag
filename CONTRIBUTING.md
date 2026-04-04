# Contributing to OmniRAG

## Development Setup

```bash
git clone https://github.com/RachEma-ux/omnirag.git
cd omnirag
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest -v                          # All tests
pytest tests/test_models.py        # Single file
pytest --cov=omnirag               # With coverage
```

## Linting

```bash
ruff check omnirag/ tests/         # Lint
ruff check --fix omnirag/ tests/   # Auto-fix
mypy omnirag/                      # Type check
bandit -r omnirag/ -s B101         # Security scan
```

## Adding an Adapter

1. Create `omnirag/adapters/<category>/<name>.py`
2. Inherit from `BaseAdapter`
3. Decorate with `@maturity_level("core"|"extended"|"experimental")`
4. Implement the relevant methods (`ingest`, `embed`, `retrieve`, `generate`, etc.)
5. Register in `omnirag/adapters/defaults.py`
6. Add tests in `tests/test_<name>.py`

Example:
```python
from omnirag.adapters.base import BaseAdapter
from omnirag.core.maturity import maturity_level

@maturity_level("core")
class MyAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "my_adapter"

    @property
    def category(self) -> str:
        return "retrieval"

    def retrieve(self, query, **kwargs):
        ...
```

## Commit Convention

```
feat: add new adapter for X
fix: resolve issue with Y
chore: update dependencies
docs: improve API documentation
```

## Agent Model

This repository follows the 5-agent operating model defined in `AGENTS.md`:
Planner -> Builder -> Reviewer -> Tester -> Governance
