"""Phase 5 tests: decay stale mastered Skills, prune deprecated Concepts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from deja.commands.forget_cmd import (
    DECAY_STALE_DAYS,
    DECAY_WEIGHT_FACTOR,
    discover_decay_candidates,
    discover_prune_targets,
)
from deja.models.graph import SkillStatus


NOW = datetime(2026, 7, 4, tzinfo=timezone.utc)


def _skill(concept: str, weight: float, status, last_practiced: datetime) -> dict:
    return {
        "id": f"skill-{concept}",
        "properties": {
            "type": "Skill",
            "concept_ref": concept,
            "mastery_weight": weight,
            "status": status.value if hasattr(status, "value") else status,
            "last_practiced_iso": last_practiced.isoformat(),
        },
    }


def _concept(name: str, deprecated: bool = False) -> dict:
    return {
        "id": f"concept-{name}",
        "properties": {"type": "Concept", "name": name, "deprecated": deprecated},
    }


def test_mastered_stale_skill_decays() -> None:
    old = NOW - timedelta(days=DECAY_STALE_DAYS + 1)
    s = _skill("recursion", 0.9, SkillStatus.MASTERED, old)
    targets = discover_decay_candidates([s], now=NOW)
    assert len(targets) == 1
    _, old_w, new_w = targets[0]
    assert old_w == 0.9
    assert abs(new_w - 0.9 * DECAY_WEIGHT_FACTOR) < 1e-6


def test_in_progress_skill_does_not_decay_even_when_stale() -> None:
    """Decay is only for mastered skills — in-progress ones stay in active recall."""
    old = NOW - timedelta(days=30)
    s = _skill("async", 0.45, SkillStatus.IN_PROGRESS, old)
    targets = discover_decay_candidates([s], now=NOW)
    assert targets == []


def test_recent_mastered_skill_does_not_decay() -> None:
    recent = NOW - timedelta(days=1)
    s = _skill("recursion", 0.9, SkillStatus.MASTERED, recent)
    targets = discover_decay_candidates([s], now=NOW)
    assert targets == []


def test_already_decaying_skill_is_skipped() -> None:
    """Idempotent: rerunning forget on a decaying Skill doesn't decay again."""
    old = NOW - timedelta(days=30)
    s = _skill("recursion", 0.4, SkillStatus.DECAYING, old)
    targets = discover_decay_candidates([s], now=NOW)
    assert targets == []


def test_force_topic_decays_even_when_recent() -> None:
    """Demo Scene 4: 'I've fully got recursion now' — user-driven decay overrides recency."""
    recent = NOW - timedelta(hours=6)
    s = _skill("recursion", 0.9, SkillStatus.MASTERED, recent)
    targets = discover_decay_candidates([s], now=NOW, force_topic="recursion")
    assert len(targets) == 1


def test_deprecated_concept_is_pruned_with_its_skill() -> None:
    old = NOW - timedelta(days=30)
    dep_c = _concept("python 2 print statement", deprecated=True)
    dep_s = _skill("python 2 print statement", 0.6, SkillStatus.MASTERED, old)
    keep_c = _concept("recursion", deprecated=False)
    keep_s = _skill("recursion", 0.9, SkillStatus.MASTERED, old)

    prune_concepts, prune_skills = discover_prune_targets(
        [dep_c, keep_c], [dep_s, keep_s]
    )
    assert [c["properties"]["name"] for c in prune_concepts] == ["python 2 print statement"]
    assert [s["properties"]["concept_ref"] for s in prune_skills] == ["python 2 print statement"]
