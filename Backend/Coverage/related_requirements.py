"""Resolve only explicitly cited supporting requirements for coverage review."""

from __future__ import annotations

from typing import Any


def index_requirements(
    requirements: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index valid source requirements without repairing duplicate or missing IDs."""

    return {
        str(requirement["id"]): requirement
        for requirement in requirements
        if requirement.get("id") is not None
    }


def resolve_supporting_requirements(
    primary_requirement_id: str,
    linked_vplan_items: list[dict[str, Any]],
    requirements_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return source text only for IDs explicitly cited by linked vPlan rows."""

    supporting_ids = sorted(
        {
            str(supporting_id)
            for item in linked_vplan_items
            for supporting_id in item.get("supporting_requirement_ids", [])
            if supporting_id is not None
            and str(supporting_id) != primary_requirement_id
            and str(supporting_id) in requirements_by_id
        }
    )

    return [
        {
            "id": supporting_id,
            "text": requirements_by_id[supporting_id].get("text")
            or requirements_by_id[supporting_id].get("description")
            or "",
            "source_section": requirements_by_id[supporting_id].get("source_section")
            or requirements_by_id[supporting_id].get("section"),
            "requirement_category": requirements_by_id[supporting_id].get(
                "requirement_category"
            ),
            "requirement_subcategory": requirements_by_id[supporting_id].get(
                "requirement_subcategory"
            ),
        }
        for supporting_id in supporting_ids
    ]
