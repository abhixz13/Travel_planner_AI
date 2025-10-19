# Folder Structure
travel_planner_ai/
│
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI application entry point
│   │   ├── api/              # API routes/endpoints
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       └── endpoints/
│   │   │           ├── __init__.py
│   │   │           └── travel.py  # Example API endpoint
│   │   ├── core/             # Backend-specific core logic (e.g., security, database connection)
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── crud/             # Create, Read, Update, Delete operations
│   │   │   └── __init__.py
│   │   ├── schemas/          # Pydantic models for request/response validation
│   │   │   └── __init__.py
│   │   └── services/         # Business logic
│   │       └── __init__.py
│   ├── tests/
│   │   └── test_main.py
│   ├── .env.example          # Example environment variables
│   └── requirements.txt      # Backend dependencies
│
├── frontend/                 # React with Vite frontend
│   ├── public/               # Static assets
│   │   └── vite.svg
│   ├── src/
│   │   ├── assets/           # Images, icons
│   │   ├── components/       # Reusable React components
│   │   │   └── App.jsx
│   │   ├── pages/            # Page-level components (e.g., Home, Dashboard)
│   │   │   └── Home.jsx
│   │   ├── services/         # API interaction logic
│   │   │   └── travelService.js
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.jsx          # Frontend entry point
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── package-lock.json     # or yarn.lock
│   └── README.md             # Frontend specific README
│
├── core/
│   ├── orchestrator.py          # LangGraph router (Coordinator Agent)
│   ├── state.py                 # Centralized session/travel schema object
│   ├── router_policy.py         # Routing rules + intent classification logic
│   └── conversation_manager.py  # Turn management, follow-up policy
│
├── agents/
│   ├── __init__.py
│   ├── clarification_agent.py   # Ensures schema completeness
│   ├── planner_agent.py       # Handles cold-start trip synthesis
│   ├── travel_discovery_agent.py# Suggests destinations (sub-agent)
│   ├── accommodation_agent.py   # Finds stay options
│   ├── activities_agent.py      # Finds events/attractions
│   ├── travel_options_agent.py  # Adds transport time/cost context
│   ├── plan_composer_agent.py   # Assembles "trip cards" from planner outputs
│   └── fallback_agent.py        # Graceful error and uncertainty handling
│
├── tools/
│   ├── __init__.py
│   ├── search_tool.py           # Web/meta search (DuckDuckGo/Tavily)
│   ├── maps_tool.py             # Distance, travel-time heuristic
│   ├── accommodation_tool.py    # Expedia/Booking-like metasearch wrapper
│   ├── activities_tool.py       # POI/Events API abstraction
│   └── utils.py                 # Common formatters, rate limiters, caching
│
├── prompts/
│   ├── orchestrator_prompts.md  # Routing + stage prompts
│   ├── clarification_prompt.md  # Ask-user templates
│   ├── discovery_prompt.md      # Destination exploration
│   ├── composer_prompt.md       # Trip card narrative templates
│   └── fallback_prompt.md       # “No data” / recovery responses
│
├── configs/
│   ├── app_config.yaml          # Global config (model, tool keys, params)
│   ├── schema_defaults.yaml     # Default values, critical fields
│   ├── routing_rules.yaml       # Static conditions for fast-path decisions
│   └── logging_config.yaml
│
├── data/
│   ├── examples/                # Example JSONs of trip plans
│   └── cache/                   # Temporary API cache (optional)
│
├── tests/
│   ├── test_orchestrator.py
│   ├── test_agents.py
│   ├── test_tools.py
│   └── fixtures/                # Sample mock responses
│
├── notebooks/                   # For prompt testing or prototyping
│
├── run.py                       # Entrypoint for CLI or server
├── requirements.txt             # Dependencies
└── README.md                    # Project overview

# State - What State captures
| Field                         | What it holds                                      | Why it’s useful                                             | Typical readers/writers                            |
| ----------------------------- | -------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| `messages: List[BaseMessage]` | Full convo history.                                | Shared context & grounding.                                 | Reader: all agents • Writer: UX/Conv agent         |
| `context: str`                | Rolling summary.                                   | Saves tokens, keeps continuity.                             | Reader: Router/Planner • Writer: Summarizer        |
| `extracted_info: Dict`        | Clean slots (origin, dates, prefs…).               | Downstream tools & planning.                                | Reader: Planner/Tools • Writer: Info-Extractor     |
| `current_plan: Dict`          | Draft/selected plan with steps.                    | Iterative refinement & branching.                           | Reader: Formatter/Next-step • Writer: Planner      |
| `tool_results: Dict`          | Cached API/tool responses.                         | Evidence reuse; avoid duplicate calls.                      | Reader: Planner/Formatter • Writer: Tool agents    |
| `metadata: Dict`              | session/user ids, trace flags, A/B bucket.         | Observability, reproducibility.                             | Reader: all • Writer: Orchestrator/Middleware      |
| `route: str`                  | Next-step hint (e.g., `generate_itinerary`).       | Clean graph control flow.                                   | Reader: Orchestrator • Writer: Router              |
| `constraints: Dict`           | **Budgets, safety, compliance, execution limits.** | **Guarantees cost/latency/safety; prunes invalid actions.** | Reader: *every node* • Writer: Orchestrator/Policy |

