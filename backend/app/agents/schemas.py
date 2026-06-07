"""Pydantic data contracts involved in agent orchestration.

Centralizing them here lets every LangGraph node depend on the single entry
point ``app.agents.schemas``; if the LLM output protocol later needs to switch
from function_calling back to json_schema, it is a one-place change.

Every agent output is required to carry a ``reasoning`` field: it is both the
landing spot for explicit CoT and a convenient way for users to see in the UI
"why it suggests this", echoing the ``reason`` field of the staging table.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class _LlmStructuredOutput(BaseModel):
    """Base class for all agent output schemas.

    The function_calling protocol of OpenAI-compatible services (especially
    DeepSeek) occasionally double-serializes list / dict fields into JSON
    strings stuffed into tool call arguments, making Pydantic throw validation
    errors like ``list_type``. Here, during the ``mode='before'`` stage, a
    lightweight parse is applied to top-level dict fields: strings that look like
    a JSON array or object are passed to ``json.loads``; on parse failure they
    are left as-is for later validation to classify.
    """

    @model_validator(mode="before")
    @classmethod
    def _coerce_stringified_json(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        for key, value in list(data.items()):
            if not isinstance(value, str):
                continue
            stripped = value.strip()
            looks_like_json = (
                (stripped.startswith("[") and stripped.endswith("]"))
                or (stripped.startswith("{") and stripped.endswith("}"))
            )
            if not looks_like_json:
                continue
            try:
                data[key] = json.loads(stripped)
            except json.JSONDecodeError:
                pass

        return data


IntentLiteral = Literal[
    "inspiration",
    "research",
    "structure",
    "simulation",
    "small_talk",
]
"""Primary intent values; small_talk is the fallback for all chit-chat that does not fall into the four agents."""

ChangeTypeLiteral = Literal[
    "create_node",
    "create_edge",
    "update_node",
    "delete_node",
    "delete_edge",
]
"""Canvas change types supported by the staging table; delete also goes through
   staging user confirmation, and HITL guarantees content is never deleted
   directly without the user, so it can share a single channel with
   create / update."""


class IntentClassification(_LlmStructuredOutput):
    """Structured output of intent_router, classifying the user message into one agent type.

    primary decides which agent node the graph routes to, and is also the basis
    for the assembler to choose the reply's main thread (tone, side-effect
    attribution). confidence is kept for frontend debugging and future threshold
    control, and does not participate in routing decisions for now.
    """

    primary: IntentLiteral
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reasoning: str = ""


class ProposedChange(_LlmStructuredOutput):
    """A canvas change the agent wants to make, entering the staging table to await user confirmation.

    ``pending_id`` assigns a temporary placeholder id to a new node within the
    same batch, so edges can reference a new node not yet persisted; the real
    node_id is backfilled at commit time, solving the "node before edge"
    dependency problem.
    """

    change_type: ChangeTypeLiteral
    target_id: str | None = None
    pending_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class WebSourceItem(BaseModel):
    """A web search hit surfaced to the frontend as a link card."""

    title: str = ""
    url: str
    snippet: str = ""


class InspirationOutput(_LlmStructuredOutput):
    """Inspiration agent output, focused on open-ended suggestions, not forced to write to the canvas."""

    reasoning: str
    suggestions: list[str] = Field(default_factory=list)
    referenced_node_ids: list[str] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)


class ResearchOutput(_LlmStructuredOutput):
    """Research / retrieval agent output, must carry citations, does not write to the canvas by default."""

    reasoning: str
    summary: str
    referenced_node_ids: list[str] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    web_sources: list[WebSourceItem] = Field(default_factory=list)


class StructureOutput(_LlmStructuredOutput):
    """Structure agent output, mainly used to produce new nodes and new relations.

    Keeps the same set of fields as InspirationOutput / ResearchOutput, so that
    chat_assembler can handle cited_node_ids uniformly without distinguishing
    intent.
    """

    reasoning: str
    summary: str
    referenced_node_ids: list[str] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)


LikelihoodLiteral = Literal["high", "medium", "low"]
"""Branch likelihood in simulation mode (compatibility with existing settings)."""


class SimulationBranch(_LlmStructuredOutput):
    """A single hypothetical direction."""

    scenario: str
    likelihood: LikelihoodLiteral
    downstream_impacts: list[str] = Field(default_factory=list)
    affected_node_ids: list[str] = Field(default_factory=list)


class SimulationOutput(_LlmStructuredOutput):
    """Simulation agent output, listing multiple directions for the user to choose from, never writes to the canvas."""

    reasoning: str
    branches: list[SimulationBranch] = Field(default_factory=list)


class ChatAssemblerOutput(_LlmStructuredOutput):
    """Chat assembler output, turning structured agent results into a natural-language bubble.

    ``staging_summary`` is an optional one-line summary rendered at the tail of
    the bubble, telling the user "I'm about to change N places", forming a
    top-to-bottom echo with the staging panel.
    """

    reply_text: str
    cited_node_ids: list[str] = Field(default_factory=list)
    staging_summary: str = ""
    web_sources: list[WebSourceItem] = Field(default_factory=list)


class ChatMetadataOutput(_LlmStructuredOutput):
    """chat_assembler step two: after reply_text is generated, extract metadata separately.

    Purpose of the split: reply_text uses token streaming generation and cannot
    use function_calling, whereas metadata like cited_node_ids /
    staging_summary need not be streamed and can be returned in one structured
    call. The two calls together still form a complete ChatAssemblerOutput, with
    the external contract unchanged.
    """

    cited_node_ids: list[str] = Field(default_factory=list)
    staging_summary: str = ""

    
class SummaryOutput(_LlmStructuredOutput):
    """Structured output of the summary compression node.

    ``key_facts`` makes the LLM explicitly list "the key facts locked in by this
    segment of conversation", both ensuring the compression misses nothing and
    making it easy for upper layers to grab "which information this summary
    preserved" in debugging or UI hints.
    """

    summary: str
    key_facts: list[str] = Field(default_factory=list)


# --- first_revision stage 4: background B-agent output contracts ---

EntityTypeLiteral = Literal["character", "world", "plot"]
"""Entity types extracted by structured_extractor; mapped to sub-graph partitions and node_type."""


class StructuredEntity(_LlmStructuredOutput):
    """An entity extracted from free-form conversation (Character / Worldbuilding / Plot)."""

    type: EntityTypeLiteral
    name: str
    attributes: dict[str, str] = Field(default_factory=dict)


class StructuredRelation(_LlmStructuredOutput):
    """A relation between entities; source_name / target_name reference entity names extracted this turn."""

    source_name: str
    target_name: str
    label: str = ""


class DeferredField(_LlmStructuredOutput):
    """A field not yet filled in and worth following up on later (fed to question_planner)."""

    entity: str
    field: str


class StructuredExtractionOutput(_LlmStructuredOutput):
    """Structured output of structured_extractor (one of the B-agents)."""

    reasoning: str = ""
    entities: list[StructuredEntity] = Field(default_factory=list)
    relations: list[StructuredRelation] = Field(default_factory=list)
    deferred_fields: list[DeferredField] = Field(default_factory=list)


class QuestionPlannerOutput(_LlmStructuredOutput):
    """Structured output of question_planner (another of the B-agents)."""

    reasoning: str = ""
    next_question: str = ""
    target_field: str = ""


WorkspaceOutputLiteral = Literal["search", "rag", "question", "feedback"]
"""Output types of the passive workspace agent; the frontend dispatches to different cards accordingly."""


class WorkspaceInspirationOutput(_LlmStructuredOutput):
    """Structured output of the lightweight workspace inspiration agent (second_revision change B / W5).

    Passive response: a single card is produced only when the user sends a
    message (optionally with referenced nodes) in the bottom dialog box.
    """

    reasoning: str = ""
    type: WorkspaceOutputLiteral = "feedback"
    content: str = ""


class SeedOutput(_LlmStructuredOutput):
    """Project seed compression output (first_revision stage 5).

    seed_compressor compresses the project's current state into this structured
    snapshot, persisting it to ProjectSeedORM, for the Chat Agent to inject at
    startup (~500 tokens scale).
    """

    worldview_summary: str = ""
    main_characters: list[str] = Field(default_factory=list)
    plot_outline: str = ""
    style_notes: str = ""