"""Validated, non-secret policy for externally orchestrated localization."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from models.user import AgentKeyMetadata
from services.user_service import iter_users


POLICY_KEY = "i18n_localization_policy"
OPERATIONS = frozenset(
    {"translate", "transliterate", "translate_then_transliterate"}
)
REVIEW_POLICIES = frozenset({"require_review", "allow_unreviewed_draft"})
MAX_MODEL_LENGTH = 200
DEFAULT_LOCALIZATION_POLICY: dict[str, Any] = {
    "enabled": False,
    "targets": {},
}


def default_localization_policy() -> dict[str, Any]:
    return deepcopy(DEFAULT_LOCALIZATION_POLICY)


def find_agent_key(key_id: Optional[str]) -> Optional[AgentKeyMetadata]:
    if not key_id:
        return None
    for user in iter_users():
        for key in user.auth.agent_keys:
            if key.key_id == key_id:
                return key
    return None


def require_active_agent_key(
    *,
    key_id: Optional[str],
    site_id: str,
    required_scopes: tuple[str, ...] = ("read", "write"),
) -> AgentKeyMetadata:
    key = find_agent_key(key_id)
    if key is None:
        raise PermissionError(
            "The bound agent key is missing or revoked; mint a new token from an active key."
        )
    if key.site_id != site_id:
        raise PermissionError("The bound agent key belongs to a different site.")
    missing = [scope for scope in required_scopes if scope not in key.scopes]
    if missing:
        raise PermissionError(
            "The bound agent key lacks required scope(s): " + ", ".join(missing)
        )
    return key


def normalize_localization_policy(
    site_id: str,
    raw: Optional[dict[str, Any]],
    *,
    default_language: str,
    configured_languages: list[str],
    validate_bindings: bool = True,
) -> dict[str, Any]:
    if raw is None:
        return default_localization_policy()
    if not isinstance(raw, dict):
        raise ValueError("i18n_localization_policy must be an object")
    unknown = set(raw) - {"enabled", "targets"}
    if unknown:
        raise ValueError(
            "Unknown i18n localization policy field(s): " + ", ".join(sorted(unknown))
        )
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("i18n_localization_policy.enabled must be a boolean")
    targets_raw = raw.get("targets", {})
    if not isinstance(targets_raw, dict):
        raise ValueError("i18n_localization_policy.targets must be an object")
    if enabled and (
        len(configured_languages) < 2 or default_language not in configured_languages
    ):
        raise ValueError(
            "Localization automation requires active i18n with the default language configured."
        )

    normalized_targets: dict[str, dict[str, Any]] = {}
    for language, target_raw in targets_raw.items():
        if not isinstance(language, str) or language != language.strip().lower():
            raise ValueError(
                "Localization policy target keys must be normalized lowercase language tags."
            )
        if language == default_language or language not in configured_languages:
            raise ValueError(
                f"Localization policy target '{language}' must be a configured non-default language."
            )
        if not isinstance(target_raw, dict):
            raise ValueError(f"Localization policy target '{language}' must be an object")
        target_unknown = set(target_raw) - {
            "operation",
            "model",
            "agent_key_id",
            "review_policy",
        }
        if target_unknown:
            raise ValueError(
                f"Unknown localization target field(s) for '{language}': "
                + ", ".join(sorted(target_unknown))
            )
        operation = target_raw.get("operation")
        if operation not in OPERATIONS:
            raise ValueError(
                f"Invalid localization operation for '{language}'. Allowed: "
                + ", ".join(sorted(OPERATIONS))
            )
        model = target_raw.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValueError(
                f"Localization target '{language}' requires a non-secret model identifier."
            )
        model = model.strip()
        if len(model) > MAX_MODEL_LENGTH:
            raise ValueError(
                f"Localization model for '{language}' exceeds {MAX_MODEL_LENGTH} characters."
            )
        agent_key_id = target_raw.get("agent_key_id")
        if not isinstance(agent_key_id, str) or not agent_key_id.strip():
            raise ValueError(
                f"Localization target '{language}' requires an immutable agent_key_id."
            )
        agent_key_id = agent_key_id.strip()
        review_policy = target_raw.get("review_policy", "require_review")
        if review_policy not in REVIEW_POLICIES:
            raise ValueError(
                f"Invalid localization review policy for '{language}'. Allowed: "
                + ", ".join(sorted(REVIEW_POLICIES))
            )
        if validate_bindings:
            try:
                require_active_agent_key(
                    key_id=agent_key_id,
                    site_id=site_id,
                    required_scopes=("read", "write"),
                )
            except PermissionError as exc:
                raise ValueError(
                    f"Invalid agent key binding for '{language}': {exc}"
                ) from exc
        normalized_targets[language] = {
            "operation": operation,
            "model": model,
            "agent_key_id": agent_key_id,
            "review_policy": review_policy,
        }
    if enabled and not normalized_targets:
        raise ValueError(
            "Enabled localization automation requires at least one target policy."
        )
    return {"enabled": enabled, "targets": normalized_targets}


def effective_localization_policy(
    site_id: str,
    raw: Optional[dict[str, Any]],
    *,
    default_language: str,
    configured_languages: list[str],
) -> dict[str, Any]:
    """Return policy plus safe binding health; never expose key secrets."""
    try:
        policy = normalize_localization_policy(
            site_id,
            raw,
            default_language=default_language,
            configured_languages=configured_languages,
            validate_bindings=False,
        )
    except ValueError as exc:
        return {
            "enabled": False,
            "targets": {},
            "policy_valid": False,
            "policy_error": str(exc),
        }
    targets: dict[str, dict[str, Any]] = {}
    for language, target in policy["targets"].items():
        resolved = dict(target)
        key = find_agent_key(target["agent_key_id"])
        binding_error: Optional[str] = None
        if key is None:
            binding_error = "missing_or_revoked"
        elif key.site_id != site_id:
            binding_error = "wrong_site"
        elif not {"read", "write"}.issubset(set(key.scopes)):
            binding_error = "missing_scope"
        resolved["agent_key_name"] = key.name if key is not None else None
        resolved["binding_valid"] = binding_error is None
        resolved["binding_error"] = binding_error
        targets[language] = resolved
    return {
        "enabled": policy["enabled"],
        "targets": targets,
        "policy_valid": True,
        "policy_error": None,
    }


def select_run_policy(
    *,
    site_id: str,
    raw: Optional[dict[str, Any]],
    default_language: str,
    configured_languages: list[str],
    actor_key_id: Optional[str],
    mode: str,
    target_languages: list[str],
) -> dict[str, Any]:
    policy = normalize_localization_policy(
        site_id,
        raw,
        default_language=default_language,
        configured_languages=configured_languages,
        validate_bindings=False,
    )
    if not policy["enabled"]:
        key = require_active_agent_key(key_id=actor_key_id, site_id=site_id)
        return {
            "policy_applied": False,
            "operation": mode,
            "model": None,
            "agent_key_id": key.key_id,
            "agent_key_name": key.name,
            "review_policy": "require_review",
        }
    selected: list[dict[str, Any]] = []
    for language in target_languages:
        target = policy["targets"].get(language)
        if target is None:
            raise PermissionError(
                f"No enabled localization policy is configured for target '{language}'."
            )
        if target["operation"] != mode:
            raise ValueError(
                f"Run mode '{mode}' does not match target '{language}' operation "
                f"'{target['operation']}'."
            )
        if target["agent_key_id"] != actor_key_id:
            raise PermissionError(
                f"Agent key is not bound to localization target '{language}'."
            )
        selected.append(target)
    signatures = {
        (
            target["operation"],
            target["model"],
            target["agent_key_id"],
            target["review_policy"],
        )
        for target in selected
    }
    if len(signatures) != 1:
        raise ValueError(
            "A translation run may combine only targets with the same operation, "
            "model, key binding, and review policy."
        )
    operation, model, key_id, review_policy = next(iter(signatures))
    key = require_active_agent_key(key_id=key_id, site_id=site_id)
    return {
        "policy_applied": True,
        "operation": operation,
        "model": model,
        "agent_key_id": key_id,
        "agent_key_name": key.name,
        "review_policy": review_policy,
    }
