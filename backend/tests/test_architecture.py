"""
Architecture guard tests — mechanical enforcement of harness rules.
Run: cd backend && pytest tests/test_architecture.py -x -q

Strategy: Pre-existing violations are recorded as baselines. Tests fail only
when NEW violations are introduced. This prevents regressions while allowing
incremental cleanup of the baseline.

To reduce a baseline: fix violations, then lower the number here.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# ── Layer Model ──────────────────────────────────────────────────────────────
# Types(0) → Config(1) → External(2) → Service/Core(3) → AI Engine(4) → API(5)

LAYER_MAP = {
    "db": 0,
    "config": 1,
    "external_apis": 2,
    "core": 3,
    "modules": 3,
    "ai_engine": 4,
    "api": 5,
}


def _file_layer(filepath: str) -> int:
    parts = filepath.replace("\\", "/").split("/")
    try:
        si = parts.index("src")
    except ValueError:
        return -1
    return LAYER_MAP.get(parts[si + 1], -1) if si + 1 < len(parts) else -1


def _import_layer(imp: str) -> int:
    for part in imp.split("."):
        if part in LAYER_MAP:
            return LAYER_MAP[part]
    return -1


def _iter_src_py(*, skip_migrations: bool = True):
    for f in SRC.rglob("*.py"):
        s = str(f)
        if "__pycache__" in s:
            continue
        if skip_migrations and "migrations" in s:
            continue
        yield f


def _extract_imports(filepath: Path) -> list[str]:
    imports = []
    try:
        for line in filepath.read_text(errors="replace").splitlines():
            m = re.match(r"^\s*(?:from|import)\s+([\w.]+)", line)
            if m:
                imports.append(m.group(1))
    except OSError:
        pass
    return imports


# ── Baselines (pre-existing violations — only decrease these) ────────────────

LAYER_VIOLATION_BASELINE = 16   # upward imports (was 47, tightened 2026-03-21)
FILE_SIZE_BASELINE = 91         # files > 500 lines
FILE_SIZE_LIMIT = 500
PIPE_NONE_BASELINE = 7          # X | None syntax occurrences
DATETIME_NOW_BASELINE = 7       # datetime.now(tz) with non-UTC tz (was 71→37→7, tightened 2026-03-23)
API_REPO_IMPORT_BASELINE = 2    # API→Repository direct imports (bypass service layer)
API_MODEL_IMPORT_BASELINE = 13  # API→Model direct imports (should use schemas)
CORE_MODULE_IMPORT_BASELINE = 20  # Core→Module imports (core must not depend on modules)
DIRECT_ANTHROPIC_BASELINE = 0   # direct AsyncAnthropic() outside core/llm/ (use get_haiku_client)
STDLIB_LOGGING_BASELINE = 179   # logging.getLogger (should use get_logger from config.logging)


# ═══════════════════════════════════════════════════════════════════════════════
# Pillar 1: Architecture as Guardrails
# ═══════════════════════════════════════════════════════════════════════════════


class TestLayerBoundaries:
    """No NEW upward layer imports may be introduced."""

    def test_no_new_upward_imports(self):
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            fl = _file_layer(rel)
            if fl == -1:
                continue
            for imp in _extract_imports(f):
                il = _import_layer(imp)
                if il != -1 and il > fl:
                    violations.append(
                        f"{rel} (layer {fl}) imports from layer {il}: {imp}"
                    )

        assert len(violations) <= LAYER_VIOLATION_BASELINE, (
            f"Layer violations increased: {len(violations)} > baseline {LAYER_VIOLATION_BASELINE}.\n"
            f"New violations:\n"
            + "\n".join(f"  - {v}" for v in violations[:20])
            + f"\n\nFix: Move shared logic to a lower layer or use an interface."
            + f"\nSee docs/ARCHITECTURE.md#layer-model"
        )


class TestFileSizeLimits:
    """No NEW files may exceed the line limit."""

    def test_no_new_oversized_files(self):
        violations = []
        for f in _iter_src_py():
            try:
                lc = sum(1 for _ in open(f))
            except (OSError, UnicodeDecodeError):
                continue
            if lc > FILE_SIZE_LIMIT:
                rel = str(f.relative_to(ROOT))
                violations.append(f"{rel}: {lc} lines")

        assert len(violations) <= FILE_SIZE_BASELINE, (
            f"Oversized files increased: {len(violations)} > baseline {FILE_SIZE_BASELINE}.\n"
            f"Limit: {FILE_SIZE_LIMIT} lines.\n"
            f"Fix: Extract helpers, split into sub-modules.\n"
            f"See docs/CONVENTIONS.md#code-organization"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Pillar 2: Documentation as System of Record (naming = documented convention)
# ═══════════════════════════════════════════════════════════════════════════════


class TestNamingConventions:

    def test_python_files_are_snake_case(self):
        violations = []
        for f in _iter_src_py():
            name = f.stem
            if name.startswith("_"):
                continue
            if not re.match(r"^[a-z][a-z0-9_]*$", name):
                violations.append(f"{f.relative_to(ROOT)}: '{name}'")

        assert not violations, (
            f"Naming violations ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations[:20])
            + "\n\nFix: Rename to snake_case."
            + "\nSee docs/CONVENTIONS.md#naming-conventions"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Pillar 3: Observability & Legibility (consistent patterns agents can follow)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDatetimeUsage:

    def test_datetime_columns_have_timezone(self):
        """SQLAlchemy DateTime columns must use timezone=True."""
        models_file = SRC / "db" / "models.py"
        if not models_file.exists():
            return

        violations = []
        for i, line in enumerate(models_file.read_text().splitlines(), 1):
            if "DateTime" in line and "Column" in line and "timezone=True" not in line:
                if "DateTime(" in line or "DateTime)" in line:
                    violations.append(f"src/db/models.py:{i}")

        assert not violations, (
            f"DateTime without timezone=True ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: Use DateTime(timezone=True). See docs/CONVENTIONS.md#datetime-rules"
        )

    def test_no_new_datetime_now_calls(self):
        """Use utc_now() from core.utils.timezone, not datetime.now()."""
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            # The utc_now() definition itself is allowed
            if "core/utils/timezone.py" in rel:
                continue
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if line.strip().startswith("#"):
                        continue
                    if "datetime.now(" in line or "datetime.utcnow(" in line:
                        violations.append(f"{rel}:{i}")
            except OSError:
                continue

        assert len(violations) <= DATETIME_NOW_BASELINE, (
            f"datetime.now() usage increased: {len(violations)} > baseline {DATETIME_NOW_BASELINE}.\n"
            f"Fix: Use utc_now() from src.core.utils.timezone instead.\n"
            f"See docs/CONVENTIONS.md#datetime-rules"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Pillar 4: Entropy Management (prevent pattern drift)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPythonCompatibility:
    """Enforce Python 3.11 compatibility rules from CONVENTIONS.md."""

    def test_no_new_pipe_none_syntax(self):
        """Ban X | None syntax — use Optional[X] instead."""
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if line.strip().startswith("#"):
                        continue
                    if re.search(r"\w+\s*\|\s*None\b", line):
                        violations.append(f"{rel}:{i}")
            except OSError:
                continue

        assert len(violations) <= PIPE_NONE_BASELINE, (
            f"X | None syntax increased: {len(violations)} > baseline {PIPE_NONE_BASELINE}.\n"
            f"Fix: Use Optional[X] instead of X | None.\n"
            f"See docs/CONVENTIONS.md#python-compatibility"
        )

    def test_no_asyncio_timeout(self):
        """Ban asyncio.timeout() — use asyncio.wait_for() instead."""
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if line.strip().startswith("#"):
                        continue
                    if "asyncio.timeout(" in line:
                        violations.append(f"{rel}:{i}")
            except OSError:
                continue

        assert not violations, (
            f"asyncio.timeout() usage found ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: Use asyncio.wait_for() instead.\n"
            + "See docs/CONVENTIONS.md#python-compatibility"
        )

    def test_no_str_enum(self):
        """Ban str(SomeEnum) — use enum.value instead."""
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if line.strip().startswith("#"):
                        continue
                    # Match str(SomeEnum.XXX) or str(var) where var is likely an enum
                    if re.search(r"\bstr\(\s*\w+\.\w+\s*\)", line):
                        # Only flag if it looks like an enum (UPPER_CASE member)
                        m = re.search(r"\bstr\(\s*(\w+)\.([A-Z_]+)\s*\)", line)
                        if m:
                            violations.append(f"{rel}:{i}: str({m.group(1)}.{m.group(2)})")
            except OSError:
                continue

        assert not violations, (
            f"str(Enum) usage found ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: Use .value instead of str().\n"
            + "See docs/CONVENTIONS.md#python-compatibility"
        )


class TestNoNewPrintStatements:
    """Production code should use logger, not print()."""

    def test_no_print_in_src(self):
        """No print() calls in source code (migrations excluded)."""
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if re.match(r"print\(", stripped):
                        violations.append(f"{rel}:{i}")
            except OSError:
                continue

        assert not violations, (
            f"print() in source code ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: Use logger.info/warning/error instead.\n"
            + "See docs/CONVENTIONS.md"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Pillar 5: Additional Enforcement (rules from CONVENTIONS.md without tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCoreModuleIsolation:
    """Core must not import from modules.* (see core/CLAUDE.md)."""

    def test_no_new_core_module_imports(self):
        """Core layer must not depend on any module (forbidden per core/CLAUDE.md)."""
        violations = []
        core_dir = SRC / "core"
        if not core_dir.exists():
            return
        for f in core_dir.rglob("*.py"):
            s = str(f)
            if "__pycache__" in s or "migrations" in s:
                continue
            rel = str(f.relative_to(ROOT))
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    # Match both top-level and deferred imports from modules
                    if re.search(r"(?:from|import)\s+[\w.]*modules\.", stripped):
                        violations.append(f"{rel}:{i}: {stripped}")
            except OSError:
                continue

        assert len(violations) <= CORE_MODULE_IMPORT_BASELINE, (
            f"Core→Module imports increased: {len(violations)} > baseline {CORE_MODULE_IMPORT_BASELINE}.\n"
            f"New violations:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: Core must not depend on modules. Use interfaces or move logic to the module.\n"
            + "See core/CLAUDE.md: Forbidden imports: modules.*"
        )


class TestWildcardImports:
    """No wildcard imports allowed (from x import *)."""

    def test_no_wildcard_imports(self):
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if re.match(r"from\s+\S+\s+import\s+\*\s*$", stripped):
                        violations.append(f"{rel}:{i}: {stripped}")
            except OSError:
                continue

        assert not violations, (
            f"Wildcard imports found ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: Import specific names instead of using 'import *'.\n"
            + "See docs/CONVENTIONS.md#import-rules"
        )


class TestAPILayerIsolation:
    """API layer must not import repositories or models directly."""

    def test_no_new_api_repo_imports(self):
        """API routes must access data through services, not repositories."""
        violations = []
        api_dir = SRC / "api"
        if not api_dir.exists():
            return
        for f in api_dir.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            rel = str(f.relative_to(ROOT))
            for imp in _extract_imports(f):
                if "repository" in imp.lower() or "repositories" in imp.lower():
                    violations.append(f"{rel}: imports {imp}")

        assert len(violations) <= API_REPO_IMPORT_BASELINE, (
            f"API→Repository imports increased: {len(violations)} > baseline {API_REPO_IMPORT_BASELINE}.\n"
            f"New violations:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: Access data through service layer, not repositories.\n"
            + "See docs/CONVENTIONS.md#import-rules and api/CLAUDE.md"
        )

    def test_no_new_api_model_imports(self):
        """API route-level (not inline) imports of SQLAlchemy models."""
        violations = []
        api_dir = SRC / "api"
        if not api_dir.exists():
            return
        for f in api_dir.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            rel = str(f.relative_to(ROOT))
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    # Only match top-level imports (not indented/deferred)
                    if not line[0:1].isalpha():
                        continue
                    # Match 'from ...modules.xxx.models' at module level
                    if re.match(r"from\s+[\w.]*modules\.\w+\.models\b", stripped):
                        violations.append(f"{rel}:{i}: {stripped}")
            except OSError:
                continue

        assert len(violations) <= API_MODEL_IMPORT_BASELINE, (
            f"API→Model top-level imports increased: {len(violations)} > baseline {API_MODEL_IMPORT_BASELINE}.\n"
            f"New violations:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: Use Pydantic schemas, not SQLAlchemy models in API layer.\n"
            + "See api/CLAUDE.md: Forbidden imports: modules.*.models"
        )


class TestImportConventions:
    """Enforce import style rules from CONVENTIONS.md."""

    def test_no_absolute_imports_within_src(self):
        """Within backend/src/, use relative imports (not 'from src.xxx')."""
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            try:
                in_docstring = False
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    stripped = line.strip()
                    # Skip docstrings and comments
                    if '"""' in stripped or "'''" in stripped:
                        if stripped.count('"""') == 1 or stripped.count("'''") == 1:
                            in_docstring = not in_docstring
                        continue
                    if in_docstring or stripped.startswith("#"):
                        continue
                    # Only match actual import statements at column 0
                    if not line[0:1].isalpha():
                        continue
                    if re.match(r"from\s+src\.", stripped):
                        violations.append(f"{rel}:{i}")
            except OSError:
                continue

        assert not violations, (
            f"Absolute 'from src.' imports within src/ ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations[:20])
            + "\n\nFix: Use relative imports within backend/src/.\n"
            + "See docs/CONVENTIONS.md#import-rules"
        )


class TestAPIRouteNaming:
    """API routes must use kebab-case URLs."""

    def test_route_paths_are_kebab_case(self):
        """All API route decorators must use kebab-case paths."""
        violations = []
        api_dir = SRC / "api"
        if not api_dir.exists():
            return
        for f in api_dir.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            rel = str(f.relative_to(ROOT))
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    # Match route decorators: @router.get("/some_path")
                    m = re.search(
                        r'@\w+\.(get|post|put|patch|delete|api_route)\(\s*["\']([^"\']+)["\']',
                        line,
                    )
                    if m:
                        path = m.group(2)
                        # Extract path segments (skip {param} placeholders)
                        segments = [
                            seg for seg in path.split("/")
                            if seg and not seg.startswith("{")
                        ]
                        for seg in segments:
                            if "_" in seg:
                                violations.append(
                                    f"{rel}:{i}: '{path}' has underscore in '{seg}'"
                                )
                                break
            except OSError:
                continue

        assert not violations, (
            f"Non-kebab-case API routes ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations[:20])
            + "\n\nFix: Use kebab-case (hyphens) in URL paths, not underscores.\n"
            + "See docs/CONVENTIONS.md#naming-conventions"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Pillar 6: Celery Task Naming (domain prefix enforcement)
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWED_TASK_PREFIXES = (
    "assistant.",
    "secretary.",
    "events.",
    "gift.",
    "trending_gifts.",
    "reminder.",
    "scheduler.",
)


class TestCeleryTaskNaming:
    """Celery task names must use allowed domain prefixes, not Python import paths."""

    def test_task_names_use_domain_prefix(self):
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    m = re.search(r'@shared_task\(\s*name="([^"]+)"', line)
                    if not m:
                        m = re.search(r'@\w+\.task\(\s*name="([^"]+)"', line)
                    if m:
                        name = m.group(1)
                        if not name.startswith(ALLOWED_TASK_PREFIXES):
                            violations.append(f"{rel}:{i}: name=\"{name}\"")
            except OSError:
                continue

        assert not violations, (
            f"Celery tasks with non-standard prefix ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + f"\n\nAllowed prefixes: {', '.join(ALLOWED_TASK_PREFIXES)}"
            + "\nSee docs/CONVENTIONS.md#naming-conventions"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Pillar 7: LLM Client Centralization
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMClientCentralization:
    """AsyncAnthropic must only be instantiated in core/llm/, not scattered across modules."""

    def test_no_new_direct_anthropic_instantiation(self):
        """All code must use get_haiku_client() from core.llm, not AsyncAnthropic()."""
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            # Allow the factory itself
            if "core/llm/" in rel:
                continue
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if "AsyncAnthropic(" in stripped and "import" not in stripped:
                        violations.append(f"{rel}:{i}: {stripped[:80]}")
            except OSError:
                continue

        assert len(violations) <= DIRECT_ANTHROPIC_BASELINE, (
            f"Direct AsyncAnthropic() increased: {len(violations)} > baseline {DIRECT_ANTHROPIC_BASELINE}.\n"
            f"New violations:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: Use get_haiku_client() from core.llm.haiku_client.\n"
            + "See docs/CONVENTIONS.md#llm-client-access"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Pillar 8: Logging Consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoggingConsistency:
    """Use get_logger() from config.logging, not logging.getLogger()."""

    def test_no_new_stdlib_logging(self):
        """New code must use get_logger(__name__), not logging.getLogger(__name__)."""
        violations = []
        for f in _iter_src_py():
            rel = str(f.relative_to(ROOT))
            # Allow the logging config itself
            if "config/logging.py" in rel:
                continue
            try:
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if "logging.getLogger(" in stripped:
                        violations.append(f"{rel}:{i}")
            except OSError:
                continue

        assert len(violations) <= STDLIB_LOGGING_BASELINE, (
            f"logging.getLogger() usage increased: {len(violations)} > baseline {STDLIB_LOGGING_BASELINE}.\n"
            f"Fix: Use get_logger(__name__) from config.logging instead.\n"
            + "See docs/CONVENTIONS.md#logging"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Pillar 9: No Orphaned Scripts
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWED_ROOT_SCRIPTS = {
    "__init__.py",
    "conftest.py",
    "celery_app.py",
    "main.py",
}


class TestNoOrphanedScripts:
    """No ad-hoc scripts at backend/ root (use scripts/ or tests/)."""

    def test_no_orphaned_backend_scripts(self):
        backend_dir = ROOT
        violations = []
        for f in backend_dir.glob("*.py"):
            if f.name not in ALLOWED_ROOT_SCRIPTS:
                violations.append(f.name)

        assert not violations, (
            f"Orphaned scripts at backend/ root ({len(violations)}):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: Move to backend/scripts/ or backend/tests/, or delete if no longer needed."
        )
