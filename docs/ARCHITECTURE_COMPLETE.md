# Complete Architecture: Component Selection & Refinement System

## System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER MESSAGE ARRIVES                          │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
                    [extract_info agent]
                             ↓
                    [route_after_extract]
                             ↓
         ┌───────────────────┼───────────────────┐
         ↓                   ↓                   ↓
    [Refinement?]       [Clarify?]          [Discover?]
         │                   │                   │
         YES                YES                 YES
         ↓                   ↓                   ↓
   refine_itinerary → END  ask_more → END  discover_destination
         ↑                                       ↓
         │                                  generate_plan
         │                                       ↓
         │                                  run_research
         │                                       ↓
         │                                compose_response
         │                                       ↓
         │                                      END
         │                                       │
         └───────────────────────────────────────┘
              (User sends new message: "I prefer hotel 2")
```

## Component Registry: How IDs Are Maintained

### 1. Initial Registration (Plan Composer)

```python
# agents/plan_composer_agent.py - compose_itinerary()

Generated Text:
┌─────────────────────────────────────────────┐
│ ## 🏨 Where to Stay                          │
│                                               │
│ 1. InterContinental The Clement - $400/night │
│ 2. Portola Hotel - $300/night                │
│ 3. Monterey Beach Hotel - $250/night         │
└─────────────────────────────────────────────┘
         ↓
_parse_and_register_components()
         ↓
register_component(state, {
    "name": "InterContinental The Clement",
    "price_range": "$400/night",
    "alternatives": [
        {"name": "Portola Hotel", "price": "$300/night"},
        {"name": "Monterey Beach Hotel", "price": "$250/night"}
    ]
}, component_type="accommodation")
         ↓
Stored in State:
┌──────────────────────────────────────────────┐
│ state["itinerary_components"] = {            │
│   "accommodation": {                         │
│     "component_id": "accommodation_main_abc" │ ← UNIQUE ID
│     "name": "InterContinental The Clement",  │
│     "selected": False,                       │ ← Not yet selected
│     "alternatives": [Hotel 2, Hotel 3]       │ ← No IDs yet
│   }                                          │
│ }                                            │
└──────────────────────────────────────────────┘
```

### 2. User Selection (Refinement Agent)

```python
# User: "I prefer hotel 2"

refine_itinerary() → detect_refinement_intent()
         ↓
{"action": "select_hotel", "selection_index": 1}
         ↓
handle_hotel_selection(state, 1)
         ↓
# Get current and alternatives
current_hotel = state["itinerary_components"]["accommodation"]
selected_hotel = current_hotel["alternatives"][1]  # Hotel 2

# Rebuild alternatives list
new_alternatives = [
    current_hotel,        # Hotel 1 becomes alternative
    alternatives[0],      # Hotel 3 stays alternative
]

# Re-register with new component_id
register_component(state, {
    "name": selected_hotel["name"],  # "Portola Hotel"
    "price_range": selected_hotel["price"],
    "alternatives": new_alternatives,
    "selected": True  # ← MARKED AS SELECTED BY USER
}, component_type="accommodation")
         ↓
Updated State:
┌──────────────────────────────────────────────┐
│ state["itinerary_components"] = {            │
│   "accommodation": {                         │
│     "component_id": "accommodation_main_xyz" │ ← NEW ID
│     "name": "Portola Hotel",                 │ ← SWAPPED
│     "selected": True,                        │ ← USER CHOSE THIS
│     "alternatives": [Hotel 1, Hotel 3]       │ ← Reordered
│   }                                          │
│ }                                            │
└──────────────────────────────────────────────┘
```

### 3. Activity Swapping

```python
# User: "Swap the morning activity on day 1 for whale watching"

refine_itinerary() → detect_refinement_intent()
         ↓
{"action": "swap_activity", "target": "morning activity day 1"}
         ↓
# Use natural language lookup
comp_id, comp = find_component(state, "morning activity day 1")
         ↓
Found: component_id = "day1_morning_activity_def456"
       name = "Monterey Bay Aquarium"
         ↓
# Mark for replacement
update_component(state, comp_id, {
    "status": "pending_replacement",
    "replacement_request": "whale watching"
})
         ↓
# Trigger discovery agent to research whale watching
state["pending_actions"].append({
    "type": "activity_swap",
    "component_id": "day1_morning_activity_def456",
    "user_request": "whale watching"
})
```

## Complete User Journey Example

### Turn 1: Initial Request
```
User: "2-3 days family trip to Monterey with toddler"
  → extract_info: Extracts details
  → route: "plan" (has destination)
  → generate_plan → run_research → compose_response
  → Outputs full itinerary with 3 hotel options
  → Registers: accommodation (Hotel 1 primary), all activities with IDs
  → Sets: ui_flags["itinerary_presented"] = True
  → END (waits for user response)
```

### Turn 2: Hotel Selection
```
User: "I prefer hotel 2"
  → extract_info runs
  → route_after_extract checks:
      - itinerary_components exists? ✓
      - itinerary_presented = True? ✓
      - detect_refinement_intent()? ✓ "select_hotel"
  → route: "refine"
  → refine_itinerary:
      - Swaps accommodation components
      - Marks selected: True
      - Responds: "Updated to Portola Hotel"
  → END (waits for user response)
```

### Turn 3: Activity Swap
```
User: "Can we skip the aquarium and do whale watching instead?"
  → extract_info runs
  → route_after_extract → "refine"
  → refine_itinerary:
      - find_component("aquarium") → "day1_morning_activity_def456"
      - update_component: mark as "pending_replacement"
      - Stores pending action
      - Responds: "Got it! Let me find whale watching options"
  → (Next turn would research & swap)
```

### Turn 4: Finalization
```
User: "Perfect, looks good!"
  → extract_info runs
  → route_after_extract checks refinement
  → check_ready_to_finalize() → True (keywords: "perfect", "looks good")
  → refine_itinerary:
      - Marks: ui_flags["confirmed_final"] = True
      - Generates final summary with ONLY selected components
      - Responds: "Great! Your finalized itinerary..."
```

## Key Functions & Their Purpose

### Component Registry (`core/component_registry.py`)

| Function | Purpose | Used By |
|----------|---------|---------|
| `generate_component_id()` | Create unique IDs | Plan Composer, Refinement Agent |
| `register_component()` | Store component with ID | Plan Composer (initial), Refinement (swaps) |
| `find_component(state, "day 1 dinner")` | Natural language lookup | Refinement Agent |
| `get_component(state, id)` | Get by exact ID | Refinement Agent |
| `update_component(state, id, {...})` | Modify component data | Refinement Agent |
| `list_components_by_type()` | Filter components | Finalization Agent |

### Refinement Agent (`agents/refinement_agent.py`)

| Function | Purpose |
|----------|---------|
| `detect_refinement_intent()` | Parse user requests for selections |
| `handle_hotel_selection()` | Swap primary hotel with alternative |
| `handle_activity_swap()` | Mark activity for replacement |
| `finalize_selections()` | Generate final itinerary summary |
| `check_ready_to_finalize()` | Detect confirmation keywords |

### Router Policy (`core/router_policy.py`)

```python
def route_after_extract(state):
    # NEW: Check for refinement first
    if itinerary_exists and user_wants_to_refine:
        return "refine"

    # Existing logic
    if clarification_incomplete:
        return "ask_more"
    if no_destination:
        return "discover"
    return "plan"
```

## State Tracking

### UI Flags
```python
state["ui_flags"] = {
    "itinerary_presented": True,    # Set by plan_composer after generating
    "has_selections": True,          # Set by refinement_agent after user selection
    "confirmed_final": True,         # Set when user confirms final plan
    "confirmed": True                # Set by clarification agent
}
```

### Component Status
```python
component = {
    "component_id": "day1_morning_activity_abc",
    "status": "proposed",            # Default
    "status": "pending_replacement", # Marked by refinement agent
    "status": "confirmed",           # User has finalized
    "selected": True,                # User explicitly chose this
}
```

## Benefits of This Architecture

1. **Flexible Selection**: Natural language references work → "the hotel", "day 2 dinner"
2. **Trackable Changes**: Every component has unique ID throughout lifecycle
3. **Swappable Components**: Alternatives stored with primary, easy to swap
4. **Iterative Refinement**: User can make multiple changes before finalizing
5. **LLM-Driven**: Refinement agent uses LLM to understand intent
6. **State Persistence**: All selections maintained in state across turns

## Testing the System

```bash
# Run the application
python3 run.py

# Example conversation:
User: 2-3 days family trip to Monterey with toddler
AI: [Generates full itinerary with 3 hotel options]

User: I prefer hotel 2
AI: Perfect! I've updated your accommodation to Portola Hotel.

User: Can we swap the morning activity for whale watching?
AI: Got it! Let me find whale watching options for you.

User: Looks great!
AI: [Generates finalized itinerary summary]
```

