from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from exoswarm.agents.skeptic import SafeRepairFeedback
from exoswarm.domain.enums import AgentRole, ThinkingMode
from exoswarm.domain.models import (
    CriticDecision,
    DirectorDecision,
    ObserverAssessment,
    SignalAssessment,
    SkepticDecision,
    TransitHunterBrief,
)


@dataclass(frozen=True, slots=True)
class PromptRegistration:
    role: AgentRole
    objective: str
    authority_boundary: str
    allowed_vocabulary: tuple[str, ...]
    prompt_version: str
    example_set_version: str
    examples: tuple[dict[str, object], ...]
    output_schema: type[BaseModel]
    output_rules: tuple[str, ...] = ()
    thinking_mode: ThinkingMode = ThinkingMode.OFF
    max_output_tokens: int = 1_200
    thinking_max_output_tokens: int = 20_000
    timeout_seconds: float = 30.0
    thinking_timeout_seconds: float = 120.0
    per_role_call_limit: int = 2
    thinking_per_role_call_limit: int = 3


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    messages: list[dict[str, str]]
    prompt_version: str
    example_set_version: str
    prompt_template_sha256: str
    rendered_request_sha256: str


def _example(role: str, output: dict[str, object], situation: str) -> dict[str, object]:
    return {"situation": situation, "output": {"role": role, **output}}


PROMPT_REGISTRY: dict[AgentRole, PromptRegistration] = {
    AgentRole.OBSERVER: PromptRegistration(
        role=AgentRole.OBSERVER,
        objective="Assess observation and preprocessing limitations from deterministic evidence.",
        authority_boundary=(
            "Advisory only. Do not request tools, alter evidence, calculate measurements, or infer "
            "facts absent from the packet."
        ),
        allowed_vocabulary=(
            "QUALITY_ACCEPTABLE",
            "SPARSE_COVERAGE",
            "EXCESS_SCATTER",
            "PREPROCESSING_LIMITATION",
            "MISSING_QUALITY_DETAIL",
        ),
        prompt_version="observer-assessment-v2",
        example_set_version="observer-examples-v1",
        examples=(
            _example(
                "observer",
                {
                    "quality_flags": ["QUALITY_ACCEPTABLE"],
                    "preparation_concerns": ["NONE"],
                    "cited_evidence_refs": ["evidence_example_quality"],
                    "observation_limitations": "No additional limitation is supported.",
                    "questions_for_later_roles": ["Does mandatory vetting reveal ambiguity?"],
                },
                "Quality evidence reports a usable deterministic candidate.",
            ),
        ),
        output_schema=ObserverAssessment,
        output_rules=(
            "observation_limitations and questions_for_later_roles must contain no digits or "
            "numeric values",
        ),
        max_output_tokens=500,
    ),
    AgentRole.SIGNAL: PromptRegistration(
        role=AgentRole.SIGNAL,
        objective="Interpret candidate-pattern evidence using the bounded hypothesis vocabulary.",
        authority_boundary=(
            "Advisory only. Never calculate period, depth, duration, SNR, significance, or any "
            "other numerical measurement."
        ),
        allowed_vocabulary=(
            "planetary_transit",
            "eclipsing_binary",
            "background_contamination",
            "instrumental_or_variable_noise",
            "unresolved",
        ),
        prompt_version="signal-assessment-v2",
        example_set_version="signal-examples-v1",
        examples=(
            _example(
                "signal",
                {
                    "leading_hypothesis": "unresolved",
                    "alternative_hypothesis": "eclipsing_binary",
                    "ambiguity_flags": ["PERIOD_ALIAS"],
                    "cited_evidence_refs": ["evidence_example_signal"],
                    "vetting_questions": ["Can a bounded harmonic test resolve the alias?"],
                    "concise_reason": "The cited evidence leaves a period alias unresolved.",
                },
                "Candidate evidence contains an unresolved harmonic interpretation.",
            ),
        ),
        output_schema=SignalAssessment,
        output_rules=(
            "concise_reason and vetting_questions must contain no digits or numeric values",
        ),
        max_output_tokens=500,
    ),
    AgentRole.TRANSIT_HUNTER: PromptRegistration(
        role=AgentRole.TRANSIT_HUNTER,
        objective="Frame the strongest bounded vetting question for the supplied candidate.",
        authority_boundary=(
            "Advisory only. Rank only action names present in available_experiments; never execute "
            "or authorize an action."
        ),
        allowed_vocabulary=(
            "VIABLE_FOR_VETTING",
            "AMBIGUOUS",
            "WEAK_SIGNAL",
            "LIKELY_FALSE_POSITIVE",
        ),
        prompt_version="transit-hunter-brief-v2",
        example_set_version="transit-hunter-examples-v1",
        examples=(
            _example(
                "transit_hunter",
                {
                    "focus_candidate_id": "candidate_example",
                    "viability_code": "AMBIGUOUS",
                    "ambiguity_codes": ["ODD_EVEN_TENSION"],
                    "strongest_vetting_question": "Does the allowed action resolve the tension?",
                    "cited_evidence_refs": ["evidence_example_vetting"],
                    "ranked_action_names": ["harmonic_test", "stop"],
                },
                "A candidate survives mandatory checks with a remaining ambiguity.",
            ),
        ),
        output_schema=TransitHunterBrief,
        output_rules=(
            "strongest_vetting_question must contain no digits or numeric values",
        ),
        max_output_tokens=500,
    ),
    AgentRole.DIRECTOR: PromptRegistration(
        role=AgentRole.DIRECTOR,
        objective="Ratify the exact deterministic route and publish a grounded mission brief.",
        authority_boundary=(
            "The authorized_route and deterministic_disposition are binding. Echo them exactly. "
            "Never authorize tools, alter disposition, or invent a route or measurement."
        ),
        allowed_vocabulary=(
            "observer",
            "signal",
            "transit_hunter",
            "skeptic",
            "critic",
            "NONE",
            "SPECIALIST_DISAGREEMENT",
            "EVIDENCE_AMBIGUITY",
            "LIMITED_OBSERVATION_QUALITY",
        ),
        prompt_version="director-ratification-v2",
        example_set_version="director-examples-v1",
        examples=(
            _example(
                "director",
                {
                    "phase": "briefing",
                    "authorized_route": "CALL_SKEPTIC",
                    "deterministic_disposition": None,
                    "focus_hypothesis": "eclipsing_binary",
                    "requested_handoffs": ["skeptic", "critic"],
                    "cited_evidence_refs": ["evidence_example_route"],
                    "conflict_codes": ["EVIDENCE_AMBIGUITY"],
                    "mission_brief": "Test the cited unresolved alternative within the route.",
                },
                "The controller binds the next route to CALL_SKEPTIC.",
            ),
        ),
        output_schema=DirectorDecision,
        output_rules=(
            "focus_hypothesis must exactly copy one allowed_focus_hypotheses entry",
            "mission_brief must contain no digits or numeric values",
        ),
        max_output_tokens=600,
    ),
    AgentRole.SKEPTIC: PromptRegistration(
        role=AgentRole.SKEPTIC,
        objective=(
            "Choose the available, affordable, unexecuted action that best discriminates the "
            "strongest unresolved non-planetary alternative."
        ),
        authority_boundary=(
            "Request only a supplied action. Deterministic Python owns measurements, costs, "
            "permissions, execution, and scientific state."
        ),
        allowed_vocabulary=(
            "HARMONIC_ALIAS_UNRESOLVED",
            "CONTAMINATION_UNRESOLVED",
            "ODD_EVEN_UNRESOLVED",
            "SECONDARY_UNRESOLVED",
            "LOW_INFORMATION_VALUE",
            "BASELINE_SUFFICIENT",
        ),
        prompt_version="skeptic-decision-v6",
        example_set_version="skeptic-examples-v1",
        examples=(
            _example(
                "skeptic",
                {
                    "requested_experiment": "harmonic_test",
                    "reason_code": "HARMONIC_ALIAS_UNRESOLVED",
                    "supporting_evidence_refs": ["evidence_example_harmonic"],
                    "contradicting_evidence_refs": [],
                },
                "A harmonic ambiguity remains and harmonic_test is available.",
            ),
            _example(
                "skeptic",
                {
                    "requested_experiment": "stop",
                    "reason_code": "BASELINE_SUFFICIENT",
                    "supporting_evidence_refs": ["evidence_example_clean"],
                    "contradicting_evidence_refs": [],
                },
                "Mandatory evidence is decisive and no useful remaining action is needed.",
            ),
        ),
        output_schema=SkepticDecision,
        output_rules=(
            "all model-authored narrative fields must contain no digits or numeric values; "
            "budget and cost fields must still copy the deterministic bindings",
            "why_cost_is_justified and concise_reason must each be at most one hundred eighty "
            "characters; expected_discriminating_result, stop_if, and every predicted_outcomes "
            "value must each be at most two hundred forty characters",
        ),
    ),
    AgentRole.CRITIC: PromptRegistration(
        role=AgentRole.CRITIC,
        objective="Independently approve, revise, or veto the exact Skeptic proposal.",
        authority_boundary=(
            "Use deterministic evidence plus the proposal only. Do not use Director or specialist "
            "preferences and never invent measurements. Check relevance, duplication, "
            "preconditions, cost justification, and whether outcomes discriminate alternatives."
        ),
        allowed_vocabulary=(
            "APPROVE",
            "REVISE",
            "VETO",
            "PROPOSAL_RELEVANT",
            "PROPOSAL_REDUNDANT",
            "PROPOSAL_IRRELEVANT",
            "PRECONDITION_UNSUPPORTED",
            "COST_NOT_JUSTIFIED",
        ),
        prompt_version="critic-review-v5",
        example_set_version="critic-examples-v1",
        examples=(
            _example(
                "critic",
                {
                    "verdict": "APPROVE",
                    "reason_code": "PROPOSAL_RELEVANT",
                    "supporting_evidence_refs": ["evidence_example_review"],
                    "contradicting_evidence_refs": [],
                },
                "The proposal directly tests the unresolved alternative and is not redundant.",
            ),
            _example(
                "critic",
                {
                    "verdict": "VETO",
                    "reason_code": "PROPOSAL_IRRELEVANT",
                    "supporting_evidence_refs": ["evidence_example_veto"],
                    "contradicting_evidence_refs": [],
                },
                "The proposed action cannot discriminate the current alternatives.",
            ),
        ),
        output_schema=CriticDecision,
        output_rules=("concise_reason must contain no digits or numeric values",),
        max_output_tokens=700,
    ),
}


def _canonical(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _template_payload(registration: PromptRegistration) -> dict[str, object]:
    payload: dict[str, object] = {
        "role": registration.role.value,
        "objective": registration.objective,
        "authority_boundary": registration.authority_boundary,
        "allowed_vocabulary": registration.allowed_vocabulary,
        "prompt_version": registration.prompt_version,
        "example_set_version": registration.example_set_version,
        "examples": registration.examples,
        "output_schema": registration.output_schema.model_json_schema(),
        "stable_sections": (
            "role_and_objective",
            "authority_boundary",
            "allowed_vocabulary",
            "evidence_grounding",
            "exact_output_bindings",
            "concise_rationale",
            "strict_output_schema",
            "canonical_examples",
            "dynamic_context",
        ),
    }
    if registration.output_rules:
        payload["role_specific_output_rules"] = registration.output_rules
    return payload


def prompt_template_sha256(role: AgentRole | str) -> str:
    registration = registration_for(role)
    return hashlib.sha256(_canonical(_template_payload(registration))).hexdigest()


def registration_for(role: AgentRole | str) -> PromptRegistration:
    return PROMPT_REGISTRY[AgentRole(role)]


def effective_output_token_limit(
    role: AgentRole | str,
    *,
    configured_max_output_tokens: int,
    thinking_mode: ThinkingMode | Literal["off", "on", "auto"],
) -> int:
    """Return the bounded role cap, with dedicated reasoning headroom when enabled."""

    registration = registration_for(role)
    role_limit = (
        registration.thinking_max_output_tokens
        if ThinkingMode(thinking_mode) == ThinkingMode.ON
        else registration.max_output_tokens
    )
    return min(configured_max_output_tokens, role_limit)


def effective_timeout_seconds(
    role: AgentRole | str,
    *,
    configured_timeout_seconds: float,
    thinking_mode: ThinkingMode | Literal["off", "on", "auto"],
) -> float:
    """Keep fast chat calls tight while allowing bounded reasoning calls to finish."""

    registration = registration_for(role)
    role_timeout = (
        registration.thinking_timeout_seconds
        if ThinkingMode(thinking_mode) == ThinkingMode.ON
        else registration.timeout_seconds
    )
    return min(configured_timeout_seconds, role_timeout)


def effective_per_role_call_limit(
    role: AgentRole | str,
    *,
    thinking_mode: ThinkingMode | Literal["off", "on", "auto"],
) -> int:
    registration = registration_for(role)
    if ThinkingMode(thinking_mode) == ThinkingMode.ON:
        return registration.thinking_per_role_call_limit
    return registration.per_role_call_limit


def _binding(context: BaseModel, name: str) -> object:
    return getattr(context, name)


def render_role_prompt(
    *,
    role: AgentRole | str,
    context: BaseModel,
    output_schema: type[BaseModel],
    repair_feedback: SafeRepairFeedback | None = None,
) -> RenderedPrompt:
    registration = registration_for(role)
    if output_schema is not registration.output_schema:
        raise ValueError("output schema does not match the registered role contract")
    system = (
        f"ROLE AND SCIENTIFIC OBJECTIVE\n{registration.objective}\n\n"
        f"AUTHORITY BOUNDARY AND FORBIDDEN BEHAVIOR\n{registration.authority_boundary} "
        "Use only the sanitized context. Never expose hidden reasoning, calculate or invent "
        "scientific measurements, or return confidence percentages.\n\n"
        f"ALLOWED VOCABULARY\n{json.dumps(registration.allowed_vocabulary)}\n\n"
        "EVIDENCE GROUNDING\nCite only evidence IDs present in evidence_refs. Every substantive "
        "claim must be supported by a cited ID.\n\n"
        "EXACT OUTPUT BINDINGS\nCopy run_id, step_id, and context_version byte-for-byte. Copy any "
        "role-specific binding supplied below exactly.\n\n"
        "CONCISE RATIONALE POLICY\nReturn concise decision-useful prose only; never "
        "chain-of-thought. For Skeptic output, keep why_cost_is_justified and concise_reason "
        "within their schema limits. For Critic output, keep concise_reason at or below 300 "
        "characters.\n\n"
        "STRICT OUTPUT SCHEMA\nReturn one JSON object with no markdown or extra keys."
    )
    if registration.output_rules:
        system += (
            "\n\nROLE-SPECIFIC OUTPUT RULES\n"
            + "\n".join(f"- {rule}" for rule in registration.output_rules)
        )
    if repair_feedback is not None:
        system += " This is the single repair attempt; use only the bounded repair feedback."
    exact_bindings: dict[str, object] = {
        "run_id": _binding(context, "run_id"),
        "step_id": _binding(context, "step_id"),
        "context_version": _binding(context, "context_version"),
    }
    for name in ("authorized_route", "phase", "deterministic_disposition"):
        if hasattr(context, name):
            exact_bindings[name] = getattr(context, name)
    proposed = getattr(context, "proposed_decision", None)
    if proposed is not None:
        exact_bindings["skeptic_decision_id"] = proposed.decision_id
    payload: dict[str, object] = {
        "prompt_version": registration.prompt_version,
        "example_set_version": registration.example_set_version,
        "canonical_examples": registration.examples,
        "exact_output_bindings": exact_bindings,
        "context": context.model_dump(mode="json"),
        "output_schema": output_schema.model_json_schema(),
    }
    if registration.role == AgentRole.DIRECTOR:
        active = tuple(str(item) for item in getattr(context, "active_hypotheses", ()))
        payload["allowed_focus_hypotheses"] = list(dict.fromkeys(active or ("unresolved",)))
    if repair_feedback is not None:
        payload["repair_feedback"] = repair_feedback.model_dump(mode="json")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": _canonical(payload).decode("utf-8")},
    ]
    return RenderedPrompt(
        messages=messages,
        prompt_version=registration.prompt_version,
        example_set_version=registration.example_set_version,
        prompt_template_sha256=prompt_template_sha256(registration.role),
        rendered_request_sha256=hashlib.sha256(_canonical(messages)).hexdigest(),
    )


# Hard-coded after prompt review. A text/schema/example change must use a new version key.
PROMPT_HASH_LOCKS: dict[str, str] = {
    "observer-assessment-v2": (
        "e8201a59b616e6c74afafb483da51cb3e5e373744090766af4b21bd3456ce272"
    ),
    "signal-assessment-v2": (
        "0e025645162fc469c3164d43574f1a31e53d4833c018b954a64c62f3b4916db4"
    ),
    "transit-hunter-brief-v2": (
        "6227182f7e7ebd85d58d2e1965899b5e1b4e40edf5212347d579d72c68f205aa"
    ),
    "director-ratification-v2": (
        "13e07a1f9712bf0ff4033959afa3c72fb3d91c6d346b2d32e3b812a3a7dd0b9a"
    ),
    "skeptic-decision-v6": (
        "612bf86aef04f7433d040cd532e433b4f4426528305aae7e16750039ed30787a"
    ),
    "critic-review-v5": (
        "0bf529152db51ded48d028053b509a089133e6f0702c90fe83496711398864ff"
    ),
}


def validate_prompt_registry() -> None:
    registered_versions = {
        registration.prompt_version for registration in PROMPT_REGISTRY.values()
    }
    if set(PROMPT_HASH_LOCKS) != registered_versions:
        raise ValueError("every registered prompt version must have exactly one hash lock")
    versions: set[str] = set()
    for role, registration in PROMPT_REGISTRY.items():
        if registration.role != role:
            raise ValueError(f"role registration mismatch for {role}")
        if registration.prompt_version in versions:
            raise ValueError(f"duplicate prompt version: {registration.prompt_version}")
        versions.add(registration.prompt_version)
        locked = PROMPT_HASH_LOCKS.get(registration.prompt_version)
        if locked is not None and locked != prompt_template_sha256(role):
            raise ValueError(
                f"prompt template changed without a version bump: {registration.prompt_version}"
            )


def thinking_requested(mode: ThinkingMode | Literal["off", "on", "auto"]) -> bool:
    return ThinkingMode(mode) == ThinkingMode.ON


validate_prompt_registry()


__all__ = [
    "PROMPT_HASH_LOCKS",
    "PROMPT_REGISTRY",
    "PromptRegistration",
    "RenderedPrompt",
    "effective_output_token_limit",
    "effective_per_role_call_limit",
    "effective_timeout_seconds",
    "prompt_template_sha256",
    "registration_for",
    "render_role_prompt",
    "thinking_requested",
    "validate_prompt_registry",
]
