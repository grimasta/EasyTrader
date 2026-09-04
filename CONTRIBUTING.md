# Contributing to EasyTrader

Thank you for considering a contribution. This document defines the standards
and workflow that all contributors are expected to follow, including the
maintainer.

---

## Workflow

### Branching

All work happens on feature branches. Direct pushes to `master` are blocked.

Branch naming convention:

| Prefix | Use for |
|---|---|
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `refactor/` | Restructuring without behaviour change |
| `docs/` | Documentation only |
| `test/` | Tests only |

Examples: `feature/parquet-repository`, `fix/cooldown-fetch`, `docs/architecture`.

### Pull Requests

- Open a PR from your branch into `master`.
- CI must pass before merge — failing tests block the merge.
- Write a PR description that explains *why* the change is needed,
  not just *what* changed. The diff shows what changed.
- Self-review your own diff before requesting a merge.
- Delete the branch after merge.

### Commits

- Use the imperative mood: `Add ParquetRepository` not `Added` or `Adding`.
- One logical change per commit. Do not bundle unrelated changes.
- Reference the issue number when applicable: `Fix cooldown file read (#12)`.
- Keep the subject line under 72 characters.

---

## Code Style

### Language

Python 3.11+. All new code must be compatible with this version.

### Formatting

PEP 8. A linter (`ruff`) will be introduced in CI in a future release.
Until then, use PyCharm's built-in PEP 8 inspection or run `ruff check .`
locally before committing.

Install ruff:
```bash
pip install ruff
ruff check .
```

### Type hints

All function and method signatures must include type hints.

```python
# correct
def compute_quantity(balance: Decimal, price: Decimal, leverage: int) -> Decimal:
    ...

# incorrect
def compute_quantity(balance, price, leverage):
    ...
```

### Decimal for financial values

Use `Decimal` for all price, quantity, fee, and ratio values.
Never use `float` for financial arithmetic, floating-point precision
errors cause order rejections.

```python
# correct
price_tick_size: Decimal = Decimal("0.1")

# incorrect
price_tick_size: float = 0.1
```

Always construct `Decimal` from a string, not a float:

```python
Decimal("0.1")   # correct — exactly 0.1
Decimal(0.1)     # incorrect — inherits float imprecision
```

### Docstrings

All public classes and methods must have docstrings in NumPy style.

```python
def read(
    self,
    symbol: str,
    timeframe: str,
    from_ms: int,
    to_ms: int,
) -> list[Kline]:
    """
    Read klines for a symbol and timeframe within a time range.

    Parameters
    ----------
    symbol : str
        Canonical symbol in BASEQUOTE format, e.g. 'BTCUSDT'.
    timeframe : str
        Timeframe string, e.g. '5m', '4h'.
    from_ms : int
        Range start, inclusive, Unix epoch milliseconds.
    to_ms : int
        Range end, inclusive, Unix epoch milliseconds.

    Returns
    -------
    list[Kline]
        Kline objects in ascending timestamp order.
        Empty list if no data exists for the given range.
    """
```

### No hardcoded values

No magic numbers, paths, credentials, or constants in business logic.
All tunable values come from `core/config.py`. All secrets come from
environment variables loaded via `.env`.

---

## Testing

- Every new module must have a corresponding test file mirroring the
  source tree structure under `test/`.
- Tests must pass CI before merge.
- Test the public interface, not the implementation. Avoid reaching into
  private attributes (`_name`) unless absolutely necessary.
- Mock only external I/O: REST calls, WebSocket connections, filesystem.
  Never mock the data model — test it directly.
- Use `pytest`. No other test framework.

---

## Secrets

Never commit credentials, API keys, or real environment values.
Use `.env` locally (gitignored) and `.env.example` for documentation.
See `SETUP.md` for details.

---

## Architecture

Before making structural changes, read `Docs/ARCHITECTURE.md`.
If a change diverges from the documented architecture, update
`Docs/DesignDecisions.md` to record the decision and rationale.