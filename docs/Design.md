# Travel Planner Backend Architecture

## 1. System Overview
The Travel Planner backend is a conversational agent built on top of LangGraph. It orchestrates several specialised components—called **agents**—to collect trip information, suggest destinations, research logistics, and compose a final itinerary. The workflow is entirely state-driven: every node reads from and writes to a shared `GraphState`, allowing stateless functions to collaborate within a single dialogue turn.

```
User Turn
  └─► Conversation Manager (messages/history)
        └─► Graph Orchestrator (LangGraph)
              ├─► Clarification Agent
              ├─► Destination Discovery Agent
              ├─► Travel Planner (summary seed)
              ├─► Research Runner
              │     ├─► Travel Options Agent
              │     ├─► Accommodation Agent
              │     └─► Activities Agent
              └─► Plan Composer
```

## 2. Core Components

### 2.1 Conversation Manager (`core/conversation_manager.py`)
- **Purpose**: Entry point for a new user turn. Appends user/assistant messages to state and exposes helpers such as `last_user_message`.
- **Design Considerations**:
  - Keeps raw LangChain `BaseMessage` objects, preserving metadata for tooling or analytics.
  - Provides small helpers (trim history, add AI output) rather than centralising logic. This keeps higher-level orchestration explicit.

### 2.2 Graph State (`core/state.py`)
- **Purpose**: Typed dictionary capturing the conversation history (`messages`), extracted fields (`extracted_info`), research results (`current_plan`), and intermediate data (`tool_results`).
- **Design Considerations**:
  - Using a `TypedDict` gives lightweight type hints without a custom class hierarchy.
  - `new_state` ensures deterministic initialisation, guaranteeing all agents can assume keys exist even in partial conversations.

### 2.3 Router Policy (`core/router_policy.py`)
- **Purpose**: Decides which node to execute after the extraction step. Routes to:
  - `ask_more` when clarification is incomplete or awaiting destination selection.
  - `discover` when the user needs destination suggestions.
  - `plan` when enough structured info is available.
- **Why this design**:
  - Keeps branching logic declarative and testable.
  - Routing decisions depend solely on `GraphState`, making it easy to simulate conversation scenarios in unit tests.

### 2.4 Orchestrator (`core/orchestrator.py`)
- **Purpose**: Builds and runs the LangGraph state machine.
- **Key Responsibilities**:
  - Ensure `current_plan` is initialised only once and re-used (prevents accidental data loss).
  - Guard research sections: execute each agent only when that section is `None`.
  - Merge agent patches through `_merge_section` to maintain a single source of truth inside `current_plan`.
- **Design Considerations**:
  - The orchestrator does not hold business logic beyond scheduling; it delegates actual work to dedicated agents.
  - Idempotent research runner allows flexible re-entry (e.g., after clarifications) without re-fetching data.

### 2.5 Agents
Each agent is a pure function operating on state. They never maintain long-lived state and they communicate exclusively via returned patches.

| Agent | Path | Responsibility | Key Design Notes |
|-------|------|----------------|------------------|
| Clarification | `agents/clarification_agent.py` | Parse conversation to extract origin, dates, purpose, group; handle confirmation loop; map discovery picks into `extracted_info.destination`. | Uses hashing to avoid repeated confirmations. Sanitises weak values (`"null"`, `"unknown"`) and asks targeted follow-ups. |
| Destination Discovery | `agents/destination_discovery_agent.py` | Generate, validate, and present destination suggestions. | Sends CTA only once, stops reissuing suggestions until resolved, avoids mutating `extracted_info`. |
| Travel Planner | `agents/travel_planner_agent.py` | Seed `current_plan.summary` from extracted info. | Idempotent: refreshes summary while preserving existing research sections. |
| Travel Options | `agents/travel_options_agent.py` | Research transport logistics (flights/drives). | Returns pure patch dictionaries; skips work on acknowledgement turns. |
| Accommodation | `agents/accommodation_agent.py` | Research stays and areas. | Context built purely from structured info; returns patch only when meaningful data exists. |
| Activities | `agents/activities_agent.py` | Research destination activities. | Mirrors transport/stays behaviour to keep sections independent. |
| Plan Composer | `agents/plan_composer_agent.py` | Convert `current_plan` into final assistant message. | Reads only summarised plan, ensuring consistent user-facing output. |

### 2.6 Research Patch Contract
- **Problem Addressed**: Early versions wrote to `state["tool_results"]` and returned patches simultaneously, creating conflicting sources of truth.
- **Solution**: Each research agent now returns `{section: payload}` or `None`. The orchestrator is the only component that mutates `current_plan`.
- **Benefit**: Simplifies reasoning about data flow, eliminates duplication, and allows the orchestrator to manage retries, caching, or cross-agent dependencies centrally.

### 2.7 Logging & Configuration (`core/logging_config.py`)
- **Current defaults**: Logging is muted (disabled) unless `TRAVEL_PLANNER_LOG_LEVEL` is set. This avoids leaking debug output in production while allowing targeted debugging when needed.
- **Consideration**: Centralised helper ensures consistent formatting and limits third-party noise.

## 3. Workflow Details

1. **Conversation Start**: `run.py` initialises state and prompts user.
2. **User Turn**:
   - `handle_user_input` appends message.
   - `run_session` invokes the LangGraph app with current state.
3. **Graph Execution**:
   - `extract_travel_info` updates `extracted_info`, may confirm details or await missing fields.
   - `route_after_extract` decides next node:
     - `ask_more`: stops turn, letting conversation manager prompt user.
     - `discover_destination`: suggestion generation if destination is unknown.
     - `generate_plan`: once destination + essentials exist.
4. **Planning**:
   - `create_itinerary` refreshes summary.
   - `_run_research` triggers research agents only for sections still `None`.
   - `compose_itinerary` builds the assistant message.
5. **Response**: `handle_ai_output` writes final message back to conversation history.

## 4. Design Considerations & Trade-offs

### 4.1 LangGraph vs. Custom Orchestration
- **Why LangGraph**: Offers declarative graph wiring, built-in tracing, and retry semantics, reducing boilerplate.
- **Alternative**: Manual state machine or recursion would require more scaffolding, making it harder to visualise the flow.

### 4.2 Patch-Based Communication
- **Advantage**: Pure functions are easier to test; they return explicit diffs rather than mutating shared state.
- **Trade-off**: Requires orchestrator to merge patches carefully, but the benefits (clear ownership, single source of truth) outweigh the minimal overhead.

### 4.3 Modular Agents
- **Why**: Each domain (clarification, discovery, stays...) evolves independently—new scoring heuristics or data sources can be plugged in without touching other agents.
- **Alternative**: A monolithic agent would be simpler to wire but harder to reason about and to unit-test.

### 4.4 Confirmation Hashing
- **Problem**: Without hashing, the planner would repeatedly ask for confirmation even if nothing changed.
- **Approach**: Hashing the confirmed fields ensures idempotent confirmations. When the user acknowledges, the hash prevents future prompts until data changes.

### 4.5 CTA Gate in Discovery
- **Why**: Prevents the LLM from re-emitting destination lists on every user message, reducing clutter and keeping the conversation focused on selection.

### 4.6 Logging Suppression
- **Use Case**: Production runs shouldn’t leak debug traces. By default, all logging is disabled. Developers can opt in by setting `TRAVEL_PLANNER_LOG_LEVEL`.
- **Trade-off**: Minimal runtime observability unless the environment variable is set—but this can be toggled in a single place.

## 5. Error Handling & Resilience
- Each research agent catches network/LLM errors and returns a safe fallback patch (`{"summary": "…failed", "results": []}`), ensuring the orchestrator still records a section even on failure.
- The orchestrator can skip already-populated sections, so transient errors during clarifications don’t wipe out previous research results.
- Discovery agent uses heuristics (drive-time scoring, deduplication) yet retains fail-safe behaviour: if no suggestions, it simply returns without disrupting the flow.

## 6. Extensibility Roadmap
- **Caching Layer**: Implement per-section caching keyed by `confirmed_hash` to avoid repeated web searches.
- **Tool Result Storage**: Move raw tool payloads into a dedicated storage interface (database or object store) if long-term persistence is required.
- **Improved Validation**: Introduce Pydantic models for agent I/O to guarantee payload shape and reduce defensive coding.
- **Observability**: Add optional telemetry hooks (OpenTelemetry / LangSmith tracing) gated by configuration.

## 7. Summary
The design emphasises:
- **Deterministic state transitions** using LangGraph.
- **Pure, composable agents** that share data through structured patches.
- **Robust clarification flow** to ensure clean trip data before planning.
- **Single source of truth** in `current_plan`, enabling consistent itinerary composition.

This architecture balances flexibility (easy to swap or upgrade agents) with reliability (clear contracts and idempotent behaviour), making it a solid foundation for future enhancements to the travel planning experience.

