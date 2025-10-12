# Travel Planner AI

This project is an AI-powered travel planner that helps users organize their trips. It consists of a core AI orchestration engine, a FastAPI backend, and a React frontend.

## Project Structure

```
travel_planner_ai/
│
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── main.py           # FastAPI application entry point
│   │   ├── api/              # API routes/endpoints
│   │   ├── core/             # Backend-specific core logic (e.g., security, database connection)
│   │   ├── crud/             # Create, Read, Update, Delete operations
│   │   ├── schemas/          # Pydantic models for request/response validation
│   │   └── services/         # Business logic
│   │   
│   ├── tests/
│   ├── .env.example          # Example environment variables
│   └── requirements.txt      # Backend dependencies
│
├── frontend/                 # React with Vite frontend
│   ├── public/               # Static assets
│   ├── src/
│   │   ├── assets/           # Images, icons
│   │   ├── components/       # Reusable React components
│   │   ├── pages/            # Page-level components (e.g., Home, Dashboard)
│   │   ├── services/         # API interaction logic
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.jsx          # Frontend entry point
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── README.md             # Frontend specific README
│
├── core/                     # Core AI orchestration logic
│   ├── orchestrator.py
│   ├── state.py
│   ├── router_policy.py
│   └── conversation_manager.py
│
├── agents/                   # AI Agents for planning tasks
│   ├── clarification_agent.py
│   ├── planner_agent.py
│   ├── travel_discovery_agent.py
│   ├── accommodation_agent.py
│   ├── activities_agent.py
│   ├── travel_options_agent.py
│   ├── plan_composer_agent.py
│   └── fallback_agent.py
│
├── tools/                    # External API integration tools
│   ├── search_tool.py
│   ├── maps_tool.py
│   ├── accommodation_tool.py
│   ├── activities_tool.py
│   └── utils.py
│
├── prompts/                  # Prompt templates for AI agents
│   ├── orchestrator_prompts.md
│   ├── clarification_prompt.md
│   ├── discovery_prompt.md
│   ├── composer_prompt.md
│   └── fallback_prompt.md
│
├── configs/                  # Configuration files
│   ├── app_config.yaml
│   ├── schema_defaults.yaml
│   ├── routing_rules.yaml
│   └── logging_config.yaml
│
├── data/                     # Example data and cache
│   ├── examples/
│   └── cache/
│
├── tests/                    # Unit and integration tests
│   ├── test_orchestrator.py
│   ├── test_agents.py
│   ├── test_tools.py
│   └── fixtures/
│
├── notebooks/                # Jupyter notebooks for prototyping and testing prompts
│
├── run.py                    # Main entry point for the application
└── requirements.txt          # Python dependencies for the core and backend
```

## Getting Started

(Instructions for setting up and running the project will go here.)
