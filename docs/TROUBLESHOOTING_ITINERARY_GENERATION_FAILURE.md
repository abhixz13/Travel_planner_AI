# Troubleshooting: Itinerary Generation Failure

## Issue Summary

**User Report:** Itinerary generation fails with error message: "I encountered an issue generating your itinerary. Let me try a simpler approach..."

**Destination:** San Juan Islands
**Origin:** California
**Dates:** October 24-26, 2025 (2 days)

---

## Investigation Process

### Step 1: Enable Debug Logging

Created test script with `TRAVEL_PLANNER_LOG_LEVEL=DEBUG` to capture full error details.

### Step 2: Run Test Generation

Simulated the exact user scenario:
```python
state["extracted_info"] = {
    "origin": "California",
    "destination": "San Juan Islands",
    "departure_date": "2025-10-24",
    "return_date": "2025-10-26",
    "duration_days": 2,
    "trip_purpose": "family activities and relaxation",
    "travel_pack": "family"
}
```

### Step 3: Captured Error Logs

```
2025-10-17 15:15:51,261 [INFO] Composer generating structured itinerary...

[Attempt 1/3]
2025-10-17 15:16:11,631 [WARNING] Validation failed on attempt 1:
  3 validation errors for StructuredItinerary
  days.0.afternoon.activity
    Value error, TimeSlot must have either an activity or restaurant
  days.1.morning.activity
    Value error, TimeSlot must have either an activity or restaurant
  days.1.evening.activity
    Value error, TimeSlot must have either an activity or restaurant

[Attempt 2/3] - Retrying with error feedback
2025-10-17 15:16:36,799 [WARNING] Validation failed on attempt 2:
  2 validation errors for StructuredItinerary
  days.0.evening.activity
    Value error, TimeSlot must have either an activity or restaurant
  days.1.afternoon.activity
    Value error, TimeSlot must have either an activity or restaurant

[Attempt 3/3] - Retrying with error feedback
2025-10-17 15:16:59,502 [WARNING] Validation failed on attempt 3:
  2 validation errors for StructuredItinerary
  days.0.evening.activity
    Value error, TimeSlot must have either an activity or restaurant
  days.1.morning.activity
    Value error, TimeSlot must have either an activity or restaurant

2025-10-17 15:16:59,502 [ERROR] All generation attempts failed
```

---

## Root Cause Analysis

### Failure Point

**File:** `core/component_schemas.py`
**Location:** Lines 95-102 (TimeSlot validation)

```python
class TimeSlot(BaseModel):
    """A scheduled time slot within a day."""
    slot_name: Literal["morning", "afternoon", "evening"]
    time_range: str
    activity: Optional[Activity] = None
    restaurant: Optional[Restaurant] = None

    @field_validator('restaurant', 'activity')
    @classmethod
    def validate_has_content(cls, v, info):
        """Ensure at least one of activity or restaurant is set."""
        if info.data.get('activity') is None and v is None:
            raise ValueError("TimeSlot must have either an activity or restaurant")
        return v
```

### The Bug

**Problem:** Using `@field_validator` for cross-field validation

**Why it fails:**
1. Pydantic validates fields **in order of definition**
2. When validating `activity` field:
   - `activity` value is being checked (could be None)
   - `restaurant` field **hasn't been set yet**, so `info.data.get('activity')` is None
   - Check: `if None is None and None is None` → raises error
3. This happens even when the LLM correctly provides ONLY a restaurant (no activity)

**Example of valid data that fails validation:**
```python
TimeSlot(
    slot_name="afternoon",
    time_range="12:00 PM - 5:00 PM",
    activity=None,           # No activity
    restaurant=Restaurant(   # Has restaurant - this is valid!
        name="Doe Bay Cafe",
        cuisine="American",
        ...
    )
)
```

When Pydantic validates the `activity` field:
- `v` (activity value) = None
- `info.data.get('activity')` = None (restaurant not set yet)
- Validator incorrectly raises: "TimeSlot must have either an activity or restaurant"

### LLM Behavior

The LLM **IS** generating correct data:
- Some slots have only activities
- Some slots have only restaurants
- This is the expected behavior

The **validator is rejecting valid data** due to field-by-field validation timing.

---

## Why Retries Don't Help

The retry mechanism adds error feedback to the prompt:
```
PREVIOUS ATTEMPT FAILED - Fix these validation errors:
days.0.afternoon.activity - Value error, TimeSlot must have either an activity or restaurant
```

But the LLM can't "fix" this because:
1. The data it generated was actually correct
2. The validator is broken, not the data
3. Each retry produces similar valid data that the validator rejects

---

## Impact

**Severity:** HIGH - Itinerary generation completely broken
**Scope:** ALL itinerary generation attempts fail
**User Experience:** Users see error message instead of itinerary

---

## Solution Required

**Change:** Replace `@field_validator` with `@model_validator(mode='after')`

A model validator runs **after all fields are set**, allowing proper cross-field validation:

```python
from pydantic import model_validator

class TimeSlot(BaseModel):
    slot_name: Literal["morning", "afternoon", "evening"]
    time_range: str
    activity: Optional[Activity] = None
    restaurant: Optional[Restaurant] = None

    @model_validator(mode='after')
    def validate_has_content(self) -> 'TimeSlot':
        """Ensure at least one of activity or restaurant is set."""
        if self.activity is None and self.restaurant is None:
            raise ValueError("TimeSlot must have either an activity or restaurant")
        return self
```

**Difference:**
- `@field_validator`: Runs during field-by-field parsing (too early)
- `@model_validator(mode='after')`: Runs after all fields are set (correct timing)

---

## Verification

After fix, the same test data should:
1. Pass validation on first attempt
2. Generate complete itinerary
3. Register all components
4. Render to markdown successfully

---

## Lessons Learned

1. **Cross-field validation requires model validators**, not field validators
2. **Field validators have limited context** - they can't reliably check other fields
3. **Structured output needs careful schema design** - validation order matters
4. **Always test with realistic data** before deploying Pydantic schemas
5. **Debug logging is essential** for diagnosing validation failures

---

## Related Issues

This same pattern exists in `DayItinerary.validate_slot_name()` (lines 54-61) but doesn't cause issues because it only reads field names, not validates cross-field constraints.

---

## Next Steps

1. Fix the `TimeSlot` validator
2. Test with the original user scenario
3. Verify all 3 attempts succeed
4. Consider adding integration tests for schema validation
5. Document best practices for Pydantic validators in structured output

