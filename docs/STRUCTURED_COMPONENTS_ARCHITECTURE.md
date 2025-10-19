# Structured Components Architecture

## Overview

The itinerary system now uses **Pydantic structured output** for reliable, validated component generation. No more fuzzy parsing - all components are strongly typed and validated at generation time.

## Architecture Changes

### Before (Fuzzy Approach) ❌

```
LLM generates markdown text
    ↓
Parse with regex (fragile!)
    ↓
Maybe extract components
    ↓
Register what we found
```

**Problems:**
- Regex parsing fails if LLM changes format
- Silent component loss
- No guarantees on structure
- Backwards flow (generate → parse → structure)

### After (Structured Approach) ✅

```
LLM generates StructuredItinerary (Pydantic)
    ↓
Automatic validation
    ↓
Register ALL components (guaranteed)
    ↓
Render to markdown (Jinja2)
```

**Benefits:**
- Type-safe components
- Automatic validation
- Retry with corrections on errors
- Template-based rendering
- Forward flow (structure → render)

---

## Component Schema Hierarchy

```
StructuredItinerary
├── metadata: TripMetadata
│   ├── destination
│   ├── origin
│   ├── dates (departure, return)
│   └── travel_pack
│
├── accommodation_options: List[AccommodationOption] (exactly 3)
│   ├── name
│   ├── price_per_night
│   ├── features
│   └── description
│
├── transport: TransportOption
│   ├── mode (driving|flying|train|bus)
│   ├── duration_minutes
│   └── recommendations
│
├── days: List[DayItinerary] (1-7 days)
│   ├── day_number
│   ├── theme
│   ├── morning: TimeSlot
│   │   ├── slot_name: "morning"
│   │   ├── time_range: "9:00 AM - 12:00 PM"
│   │   └── activity OR restaurant
│   ├── afternoon: TimeSlot (12:00 PM - 5:00 PM)
│   └── evening: TimeSlot (5:00 PM - 9:00 PM)
│
└── pro_tips: List[str] (5-10 tips)
```

### Fixed Time Slots

Every day has **exactly 3 slots** with fixed time ranges:
- **Morning**: 9:00 AM - 12:00 PM
- **Afternoon**: 12:00 PM - 5:00 PM
- **Evening**: 5:00 PM - 9:00 PM

Each slot contains **either** an Activity **or** a Restaurant (validated).

---

## Core Files

### 1. `core/component_schemas.py` (NEW)

Defines all Pydantic models with validation:

```python
class Activity(BaseModel):
    name: str
    type: Literal["attraction", "outdoor", "indoor", "educational", "entertainment"]
    time_start: str  # e.g., "09:30 AM"
    duration_minutes: int = Field(ge=15, le=300)
    cost_adult: Optional[float]
    toddler_friendly: bool = True
    # ... more fields

class Restaurant(BaseModel):
    name: str
    cuisine: str
    price_range: Literal["$", "$$", "$$$", "$$$$"]
    time: str
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    toddler_friendly_features: List[str]
    # ... more fields

class TimeSlot(BaseModel):
    slot_name: Literal["morning", "afternoon", "evening"]
    time_range: str
    activity: Optional[Activity]
    restaurant: Optional[Restaurant]

    @field_validator('restaurant', 'activity')
    def validate_has_content(cls, v, info):
        """Ensure at least one is set."""
        if info.data.get('activity') is None and v is None:
            raise ValueError("TimeSlot must have either activity or restaurant")
        return v

class StructuredItinerary(BaseModel):
    """Complete validated itinerary."""
    metadata: TripMetadata
    accommodation_options: List[AccommodationOption] = Field(min_length=3, max_length=3)
    transport: TransportOption
    days: List[DayItinerary]
    pro_tips: List[str]
```

### 2. `templates/itinerary.jinja2` (NEW)

Jinja2 template for rendering structured components to markdown:

```jinja2
# 🗺️ Your {{ metadata.destination }} Adventure

## 🏨 Where to Stay
{% for hotel in accommodation_options %}
### {{ loop.index }}. {{ hotel.name }} — ${{ hotel.price_per_night }}/night
{{ hotel.description }}
**Features**:
{% for feature in hotel.features %}
- {{ feature }}
{% endfor %}
{% endfor %}

## 📅 Day-by-Day Itinerary
{% for day in days %}
### Day {{ day.day_number }} — {{ day.theme }}

**Morning ({{ day.morning.time_range }})**
{% if day.morning.activity %}
- **{{ day.morning.activity.time_start }}**: {{ day.morning.activity.name }}
  - **Duration**: {{ day.morning.activity.duration_minutes }} minutes
  {% if day.morning.activity.cost_adult %}
  - **Cost**: Adults ${{ day.morning.activity.cost_adult }}
  {% endif %}
{% endif %}
{% endfor %}
```

### 3. `core/itinerary_renderer.py` (NEW)

Renders structured components to markdown:

```python
class ItineraryRenderer:
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

    def render(self, itinerary: StructuredItinerary) -> str:
        template = self.env.get_template("itinerary.jinja2")
        context = itinerary.model_dump()
        return template.render(**context)
```

### 4. `agents/plan_composer_agent.py` (REWRITTEN)

Now generates structured output with retry logic:

```python
def compose_itinerary(state: GraphState) -> GraphState:
    # 1. Gather research data
    facts, travel, stays, acts = _gather_trip_facts(state)
    prompt = _build_structured_prompt(facts, {...})

    # 2. Generate with Pydantic structured output
    llm = ChatOpenAI(model="gpt-4o")
    structured_llm = llm.with_structured_output(StructuredItinerary)

    try:
        # 3. Generate with retry logic (max 2 retries)
        itinerary = _generate_with_retries(llm, prompt, max_retries=2)

        # 4. Register ALL components (no parsing!)
        _register_structured_components(state, itinerary)

        # 5. Render to markdown
        markdown = render_itinerary(itinerary)

        # 6. Show user
        handle_ai_output(state, markdown)

    except ValidationError:
        # Retry failed - show error
        handle_ai_output(state, "I encountered validation issues...")
```

---

## Component Registration Flow

### Before (Fuzzy)

```python
# Parse markdown with regex
hotels = _parse_hotels(text)  # Might find 0-3 hotels
activities = _parse_activities(text)  # Might miss some

# Register what we found
for hotel in hotels:
    register_component(state, hotel, "accommodation")
```

### After (Structured)

```python
def _register_structured_components(state, itinerary: StructuredItinerary):
    # GUARANTEED: Exactly 3 hotels (Pydantic validated)
    primary = itinerary.accommodation_options[0]
    alternatives = itinerary.accommodation_options[1:]

    register_component(state, {
        **primary.model_dump(),
        "alternatives": [h.model_dump() for h in alternatives],
        "selected": False
    }, "accommodation")

    # GUARANTEED: All slots filled (Pydantic validated)
    for day in itinerary.days:
        if day.morning.activity:
            register_component(
                state,
                day.morning.activity.model_dump(),
                "activity",
                day_number=day.day_number,
                time_slot="morning"
            )
        elif day.morning.restaurant:
            register_component(
                state,
                day.morning.restaurant.model_dump(),
                "restaurant",
                day_number=day.day_number,
                time_slot="morning"
            )
```

**Key Differences:**
1. ✅ No parsing - direct access to validated objects
2. ✅ Guaranteed structure - Pydantic ensures all required fields exist
3. ✅ Type safety - Can't accidentally pass wrong data
4. ✅ All components registered - No silent losses

---

## Validation & Retry Logic

### Automatic Retry on Validation Errors

```python
def _generate_with_retries(llm, prompt, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            structured_llm = llm.with_structured_output(StructuredItinerary)
            result = structured_llm.invoke(prompt)
            return result  # Success!

        except ValidationError as e:
            if attempt < max_retries:
                # Add error feedback to prompt
                prompt += f"\n\nPREVIOUS ATTEMPT FAILED - Fix:\n{e}"
                # Retry with corrections
            else:
                raise  # All retries failed
```

### Example Error Correction

```
Attempt 1:
LLM generates:
{
  "accommodation_options": [hotel1, hotel2]  # Only 2!
}

Validation Error:
"List should have at least 3 items after validation"

Attempt 2 (with error feedback):
LLM generates:
{
  "accommodation_options": [hotel1, hotel2, hotel3]  # Fixed!
}

Success!
```

---

## User Selection Flow (With Structured Components)

### 1. Initial Generation

```python
# LLM generates StructuredItinerary
itinerary = StructuredItinerary(
    accommodation_options=[hotel1, hotel2, hotel3],
    days=[...]
)

# Register: hotel1 as primary, [hotel2, hotel3] as alternatives
register_component(state, {
    ...hotel1.model_dump(),
    "alternatives": [hotel2.model_dump(), hotel3.model_dump()],
    "selected": False
}, "accommodation")

# Render to markdown
markdown = render_itinerary(itinerary)
```

### 2. User Selection

```
User: "I prefer hotel 2"

refinement_agent detects: {"action": "select_hotel", "selection_index": 1}

# Swap components
current = state["itinerary_components"]["accommodation"]
selected = current["alternatives"][1]  # hotel2

# Re-register
register_component(state, {
    ...selected,
    "alternatives": [current (hotel1), hotel3],
    "selected": True
}, "accommodation")
```

### 3. Re-rendering

```python
# Retrieve structured itinerary from state
stored_itinerary = dict_to_itinerary(state["itinerary_components"])

# Render updated version
markdown = render_itinerary(stored_itinerary)
```

---

## Testing the System

### Install Required Dependencies

```bash
pip install pydantic jinja2
```

### Run the Application

```bash
python3 run.py
```

### Example Conversation

```
User: 2-3 days family trip to Monterey with toddler
AI: [Generates structured itinerary]
    - GUARANTEED: 3 hotel options
    - GUARANTEED: All time slots filled
    - GUARANTEED: All costs, times, descriptions present

User: I prefer hotel 2
AI: Perfect! Updated to [Hotel 2 name].

User: Can we swap the morning activity on day 1?
AI: Sure! What would you like to do instead?
```

---

## Migration Notes

### Old Code Removed

The following fuzzy parsing functions have been **removed** from `plan_composer_agent.py`:

- `_parse_and_register_components()`
- `_extract_section()`
- `_parse_hotels()`
- `_extract_day_sections()`
- `_parse_time_slots()`
- `_parse_activities()`

### Backup Available

The old implementation is backed up at:
```
agents/plan_composer_agent.py.bak
```

### Breaking Changes

⚠️ **Component Storage Format Changed**

Old format (parsed from text):
```python
{
    "name": "Hotel Name",
    "description": "...",
    "price": "$400/night"  # String
}
```

New format (Pydantic validated):
```python
{
    "name": "Hotel Name",
    "description": "...",
    "price_per_night": 400  # Integer
}
```

If you have existing stored itineraries, they need migration.

---

## Benefits Summary

| Aspect | Before (Fuzzy) | After (Structured) |
|--------|----------------|-------------------|
| **Parsing** | Regex (fragile) | Pydantic (reliable) |
| **Validation** | Manual checks | Automatic |
| **Guarantees** | None | Type-safe, validated |
| **Errors** | Silent failures | Clear validation errors |
| **Rendering** | String concatenation | Jinja2 templates |
| **Component Loss** | Possible | Impossible |
| **Retry Logic** | N/A | Automatic with error feedback |
| **Maintenance** | Regex updates needed | Schema-driven |

---

## Future Enhancements

With structured components, we can now easily add:

1. **Component Alternatives**: Store multiple options for each activity
2. **Cost Tracking**: Automatic trip budget calculation
3. **Time Validation**: Ensure no scheduling conflicts
4. **Export Formats**: JSON, PDF, iCal with same structure
5. **AI Refinements**: LLM can modify specific components by ID
6. **Undo/Redo**: Track component changes over time

The foundation is now solid and extensible!
