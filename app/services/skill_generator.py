"""
skill_generator.py
------------------
Dynamic Skill Generator for Notiflow.

Creates new business skill Python files on demand and registers them in
skills/skill_registry.json.

Public API
----------
generate_skill(skill_name: str, description: str) -> dict
list_skills() -> dict

Safety rules:
  - Raises SkillAlreadyExistsError if a skill with the same name exists.
  - Skill names are normalised to snake_case.
  - Generated files follow the standard skill template.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from app.config import ROOT, REGISTRY_FILE

logger = logging.getLogger(__name__)

SKILLS_DIR = ROOT / "skills"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SkillAlreadyExistsError(Exception):
    """Raised when a skill with the given name already exists."""


# ---------------------------------------------------------------------------
# Skill file template
# ---------------------------------------------------------------------------

_SKILL_TEMPLATE = '''\
"""
{skill_name}.py
{underline}
Auto-generated business skill for Notiflow.

Description: {description}

Modify this file to implement the skill logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def {func_name}(data: dict) -> dict:
    """
    Execute the {display_name} skill.

    Args:
        data: Validated extraction dict from the orchestrator.

    Returns:
        Structured skill event dict.
    """
    logger.info("{display_name} skill executing: %s", data)

    return {{
        "event": "{event_name}",
        "data":  data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }}
'''


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_snake_case(name: str) -> str:
    """Normalise skill name to snake_case (alphanumeric + underscores only)."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def _load_registry() -> dict:
    path = Path(REGISTRY_FILE)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read registry: %s", exc)
        return {}


def _save_registry(registry: dict) -> None:
    path = Path(REGISTRY_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_skill(skill_name: str, description: str) -> dict:
    """
    Generate a new skill file and register it.

    Args:
        skill_name:  Human-readable name (e.g. "discount_skill" or "Discount Skill").
                     Normalised to snake_case automatically.
        description: One-line description stored in the registry.

    Returns:
        Registry entry dict for the new skill:
        {
            "description": str,
            "intent":      None,
            "file":        "skills/<name>.py",
            "builtin":     false
        }

    Raises:
        SkillAlreadyExistsError: If a skill with the same name already exists
                                 (either as a .py file or registry entry).
        ValueError: If skill_name is empty or invalid.

    Example:
        >>> generate_skill("discount_skill", "Apply discount to an order")
        {"description": "Apply discount...", "file": "skills/discount_skill.py", ...}
    """
    norm_name = _to_snake_case(skill_name)
    if not norm_name:
        raise ValueError(f"Invalid skill name: {skill_name!r}")

    skill_file = SKILLS_DIR / f"{norm_name}.py"
    registry   = _load_registry()

    # ── Collision guard ──────────────────────────────────────────────────────
    if norm_name in registry:
        raise SkillAlreadyExistsError(
            f"Skill '{norm_name}' already exists in the registry. "
            "Choose a different name or delete the existing entry first."
        )
    if skill_file.exists():
        raise SkillAlreadyExistsError(
            f"Skill file '{skill_file}' already exists on disk. "
            "Choose a different name or delete the existing file first."
        )

    # ── Generate file ────────────────────────────────────────────────────────
    display_name = norm_name.replace("_", " ").title()
    func_name    = norm_name
    event_name   = f"{norm_name}_executed"
    underline    = "-" * (len(norm_name) + 3)     # matches "name.py" length

    source = _SKILL_TEMPLATE.format(
        skill_name   = norm_name,
        underline    = underline,
        description  = description,
        func_name    = func_name,
        display_name = display_name,
        event_name   = event_name,
    )

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(source, encoding="utf-8")
    logger.info("Skill file created: %s", skill_file)

    # ── Register ─────────────────────────────────────────────────────────────
    entry = {
        "description": description,
        "intent":      None,          # caller can update after creation
        "file":        f"skills/{norm_name}.py",
        "builtin":     False,
    }
    registry[norm_name] = entry
    _save_registry(registry)
    logger.info("Skill '%s' registered.", norm_name)

    return entry


def list_skills() -> dict:
    """
    Return the full skill registry.

    Returns:
        Dict mapping skill_name → registry entry.
    """
    return _load_registry()