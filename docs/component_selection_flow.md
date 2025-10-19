# Component Selection & Refinement Flow

## Architecture Overview

### How Component Registry Maintains IDs

```
Initial Plan Generation (plan_composer_agent.py)
    ↓
Generates text itinerary with 3 hotels, multiple activities
    ↓
Parses text and registers components:
    - Hotel 1 → accommodation (component_id: "accommodation_main_abc123")
    - Hotel 2 → alternatives[0] (no component_id yet)
    - Hotel 3 → alternatives[1] (no component_id yet)
    - Day 1 Morning Activity → (component_id: "day1_morning_activity_def456")
    - Day 1 Afternoon Activity → (component_id: "day1_afternoon_activity_ghi789")
    - etc.
    ↓
All components stored in state["itinerary_components"]
```

### Component Storage Structure

```python
state["itinerary_components"] = {
    "metadata": {...},

    "accommodation": {
        "component_id": "accommodation_main_abc123",
        "name": "InterContinental The Clement",
        "description": "...",
        "price_range": "$400/night",
        "selected": False,  # Not yet selected by user
        "alternatives": [
            {"name": "Portola Hotel", "price": "$300/night"},
            {"name": "Monterey Beach Hotel", "price": "$250/night"}
        ]
    },

    "days": {
        "day1": {
            "morning_slot": {
                "component_id": "day1_morning_activity_def456",
                "name": "Monterey Bay Aquarium",
                "type": "activity",
                "status": "proposed"  # Not yet confirmed
            },
            "afternoon_slot": {...},
            "evening_slot": {...}
        },
        "day2": {...}
    }
}
```

## User Selection Flow

### Step 1: Initial Plan Presented

**Plan Composer Output:**
```
🏨 Where to Stay
1. InterContinental The Clement - $400/night (registered as primary)
2. Portola Hotel - $300/night (stored in alternatives)
3. Monterey Beach Hotel - $250/night (stored in alternatives)
```

### Step 2: User Makes Selection

**User input:** "I prefer hotel 2"

**Refinement Agent (`refine_itinerary()`):**
1. Detects intent: `{"action": "select_hotel", "selection_index": 1}`
2. Calls `handle_hotel_selection(state, 1)`
3. **Swaps components:**
   ```python
   # Before:
   accommodation: Hotel 1 (primary)
   alternatives: [Hotel 2, Hotel 3]

   # After:
   accommodation: Hotel 2 (primary, marked "selected": True)
   alternatives: [Hotel 1, Hotel 3]
   ```
4. Re-registers Hotel 2 with new component_id
5. Responds: "Perfect! Updated to Portola Hotel"

### Step 3: User Swaps Activity

**User input:** "Swap the morning activity on Day 1 for whale watching"

**Refinement Agent:**
1. Detects: `{"action": "swap_activity", "target": "morning activity day 1"}`
2. Uses `find_component(state, "morning activity day 1")`
3. Finds: `component_id: "day1_morning_activity_def456"`
4. Marks component: `{"status": "pending_replacement"}`
5. Stores pending action for discovery agent to find whale watching options

### Step 4: Finalization

**User input:** "Looks good, let's finalize"

**Refinement Agent:**
1. `check_ready_to_finalize()` returns True
2. Generates final summary with only SELECTED components
3. Marks all selected components with `"confirmed": True`
4. Can export to PDF/email with final selections

## Integration with Orchestrator

The orchestrator needs a new routing decision:

```python
# In core/orchestrator.py

def route_next_agent(state: GraphState) -> str:
    """Decide which agent runs next."""

    # If user is refining/selecting components
    if state.get("itinerary_components") and not state.get("ui_flags", {}).get("confirmed_final"):
        return "refinement_agent"

    # If ready to finalize
    if check_ready_to_finalize(state):
        return "finalization_agent"

    # ... existing routing logic
```

## Key Functions in Component Registry

### Used by Plan Composer (Initial Creation)
- `register_component()` - Create components with unique IDs
- `generate_component_id()` - Generate IDs like "day1_morning_activity_abc123"

### Used by Refinement Agent (User Selections)
- `find_component(state, "Day 1 morning activity")` - Natural language lookup
- `get_component(state, component_id)` - Get by ID
- `update_component(state, component_id, {"selected": True})` - Mark selections
- `list_components_by_type(state, "restaurant")` - Get all restaurants

### Used by Finalization Agent
- `list_components_by_day(state, 1)` - Get Day 1 schedule
- Filter by `component.get("selected")` or `component.get("confirmed")`

## Example Complete Flow

```
1. User: "2-3 days family trip to Monterey"
   → Clarification Agent extracts info

2. User: "Yes, looks correct"
   → Discovery Agent researches hotels/activities

3. Plan Composer generates itinerary
   → Registers: 1 primary hotel, 2 alternatives
   → Registers: All activities with unique IDs
   → User sees: Complete itinerary with options

4. User: "I prefer hotel 2"
   → Refinement Agent swaps accommodation
   → Hotel 2 becomes primary with component_id
   → Hotel 1 moved to alternatives

5. User: "Can we skip the aquarium and do whale watching?"
   → Refinement Agent marks aquarium as "pending_replacement"
   → Discovery Agent searches for whale watching
   → Refinement Agent swaps components

6. User: "Perfect, let's book it"
   → Finalization Agent checks all selections
   → Generates final itinerary with ONLY selected/confirmed components
   → Exports to PDF/email
```

## Current Gap

**MISSING:** The orchestrator doesn't route to refinement agent yet!

You need to add to `core/orchestrator.py`:
```python
from agents.refinement_agent import refine_itinerary

# In the graph/workflow
graph.add_node("refinement_agent", refine_itinerary)
```

This completes the selection loop.
