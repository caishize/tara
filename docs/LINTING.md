# Secretary Linting

## Backend (Python)

### Formatter: Black
```bash
cd backend && black src/ tests/          # Format
cd backend && black --check src/ tests/  # Check only
```
Config: defaults (line length 88, Python 3.11 target)

### Linter: Flake8
```bash
cd backend && flake8 src/ tests/
```

### Type Checker: Mypy
```bash
cd backend && mypy src/
```

### Full Lint Check
```bash
cd backend && black --check src/ tests/ && flake8 src/ tests/ && mypy src/
```

## Mobile (Dart/Flutter)

### Analyzer
```bash
cd mobile && flutter analyze
```

### Formatter
```bash
cd mobile && dart format lib/ test/
```

## Pre-commit Hooks

See `.pre-commit-config.yaml` for automatic enforcement at commit time.
Includes: Black formatter, Flake8 linter, architecture guard tests.

## CI/CD Enforcement

GitHub Actions runs all linting on push/PR to main/develop.
See `.github/workflows/test.yml`.
