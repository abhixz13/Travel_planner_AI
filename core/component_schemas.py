"""
Pydantic schemas for structured itinerary components.
All components are strongly typed with validation.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Literal, Optional
from datetime import time


# ======================== Base Components ========================

class AccommodationOption(BaseModel):
    """A single hotel/lodging option for the trip."""
    name: str = Field(..., description="Hotel name")
    description: str = Field(..., description="Why this is good for the trip (2-3 sentences)")
    price_per_night: int = Field(..., ge=0, description="Price per night in USD")
    features: List[str] = Field(default_factory=list, description="Family-friendly features")
    location: str = Field(..., description="Area/neighborhood")
    booking_url: Optional[str] = Field(None, description="Booking link if available")

    @field_validator('features')
    @classmethod
    def validate_features(cls, v: List[str]) -> List[str]:
        """Ensure at least one feature."""
        if not v:
            return ["Family-friendly"]
        return v[:5]  # Max 5 features


class TransportOption(BaseModel):
    """Transportation details for getting to destination."""
    mode: Literal["driving", "flying", "train", "bus", "hybrid"] = Field(..., description="Transport mode")
    duration_minutes: Optional[int] = Field(None, ge=0, description="Travel duration")
    cost_per_person: Optional[int] = Field(None, ge=0, description="Cost per person in USD (e.g., per adult)")
    total_cost_estimate: Optional[int] = Field(None, ge=0, description="Total estimated cost for entire family/group in USD")
    cost_notes: str = Field(default="", description="Price breakdown explanation (e.g., 'for 2 adults, 1 toddler')")
    description: str = Field(..., description="Route details and tips")
    recommendations: List[str] = Field(default_factory=list, description="Travel tips")
    recommended: bool = Field(default=False, description="Recommended option based on traveler needs")
    pros_cons: str = Field(default="", description="Brief pros/cons summary for this option")


class Activity(BaseModel):
    """A single activity at a specific time."""
    name: str = Field(..., description="Activity name")
    type: Literal["attraction", "outdoor", "indoor", "educational", "entertainment"] = Field(
        ..., description="Activity category"
    )
    time_start: str = Field(..., description="Start time (e.g., '09:00 AM')")
    duration_minutes: int = Field(..., ge=15, le=300, description="Duration in minutes")
    cost_adult: Optional[float] = Field(None, ge=0, description="Adult ticket price")
    cost_child: Optional[float] = Field(None, ge=0, description="Child ticket price (3-12)")
    free_under_3: bool = Field(True, description="Free for toddlers under 3")
    description: str = Field(..., description="What to expect (2-3 sentences)")
    tips: List[str] = Field(default_factory=list, description="Practical tips")
    toddler_friendly: bool = Field(True, description="Suitable for toddlers")

    @field_validator('tips')
    @classmethod
    def validate_tips(cls, v: List[str]) -> List[str]:
        """Limit tips to max 3."""
        return v[:3]


class Restaurant(BaseModel):
    """A dining recommendation at a specific time."""
    name: str = Field(..., description="Restaurant name")
    cuisine: str = Field(..., description="Cuisine type")
    price_range: Literal["$", "$$", "$$$", "$$$$"] = Field(..., description="Price range")
    time: str = Field(..., description="Meal time (e.g., '12:30 PM')")
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] = Field(..., description="Meal type")
    toddler_friendly_features: List[str] = Field(
        default_factory=list,
        description="Kid-friendly features (high chairs, kids menu, etc.)"
    )
    description: str = Field(..., description="Why recommended (1-2 sentences)")
    average_cost_per_person: Optional[int] = Field(None, ge=0, description="Average cost per person")

    @field_validator('toddler_friendly_features')
    @classmethod
    def validate_features(cls, v: List[str]) -> List[str]:
        """Ensure at least one toddler feature."""
        if not v:
            return ["Kids welcome"]
        return v[:4]


# ======================== Time Slots ========================

class TimeSlot(BaseModel):
    """A scheduled time slot within a day."""
    slot_name: Literal["morning", "afternoon", "evening"] = Field(..., description="Time period")
    time_range: str = Field(..., description="Time range (e.g., '9:00 AM - 12:00 PM')")
    activity: Optional[Activity] = Field(None, description="Activity in this slot")
    restaurant: Optional[Restaurant] = Field(None, description="Restaurant in this slot")

    @model_validator(mode='after')
    def validate_has_content(self) -> 'TimeSlot':
        """Ensure at least one of activity or restaurant is set."""
        if self.activity is None and self.restaurant is None:
            raise ValueError("TimeSlot must have either an activity or restaurant")
        return self


class DayItinerary(BaseModel):
    """Complete itinerary for a single day."""
    day_number: int = Field(..., ge=1, le=7, description="Day number (1-7)")
    theme: str = Field(..., description="Day theme (e.g., 'Marine Exploration')")
    morning: TimeSlot = Field(..., description="Morning slot (9am-12pm)")
    afternoon: TimeSlot = Field(..., description="Afternoon slot (12pm-5pm)")
    evening: TimeSlot = Field(..., description="Evening slot (5pm-9pm)")

    @field_validator('morning', 'afternoon', 'evening')
    @classmethod
    def validate_slot_name(cls, v: TimeSlot, info) -> TimeSlot:
        """Ensure slot_name matches the field name."""
        field_name = info.field_name
        if v.slot_name != field_name:
            v.slot_name = field_name
        return v


# ======================== Complete Itinerary ========================

class TripMetadata(BaseModel):
    """Trip overview information."""
    destination: str = Field(..., description="Primary destination")
    origin: str = Field(..., description="Starting location")
    departure_date: str = Field(..., description="Departure date (YYYY-MM-DD)")
    return_date: str = Field(..., description="Return date (YYYY-MM-DD)")
    duration_days: int = Field(..., ge=1, le=7, description="Trip duration")
    purpose: str = Field(..., description="Trip purpose")
    travel_pack: Literal["solo", "couple", "family", "friends", "other"] = Field(
        ..., description="Travel party type"
    )


class StructuredItinerary(BaseModel):
    """
    Complete structured itinerary with all components.
    This is the canonical representation that gets registered in component_registry.
    """
    metadata: TripMetadata = Field(..., description="Trip overview")

    accommodation_options: List[AccommodationOption] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly 3 hotel options for user to choose from"
    )

    transport_options: List[TransportOption] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="1-3 transport options (recommended option should be first)"
    )

    days: List[DayItinerary] = Field(
        default_factory=list,
        max_length=7,
        description="Day-by-day itinerary (empty until hotel selected)"
    )

    pro_tips: List[str] = Field(
        default_factory=list,
        description="General trip tips (5-10 items)"
    )

    @field_validator('days')
    @classmethod
    def validate_days_sequential(cls, v: List[DayItinerary]) -> List[DayItinerary]:
        """Ensure days are numbered sequentially from 1 (if any days exist)."""
        if not v:  # Allow empty list
            return v
        sorted_days = sorted(v, key=lambda d: d.day_number)
        for i, day in enumerate(sorted_days, start=1):
            if day.day_number != i:
                day.day_number = i
        return sorted_days

    @field_validator('pro_tips')
    @classmethod
    def validate_tips(cls, v: List[str]) -> List[str]:
        """Limit to 10 tips."""
        return v[:10]


# ======================== Helper Functions ========================

def validate_itinerary(data: dict) -> StructuredItinerary:
    """
    Validate raw dictionary against StructuredItinerary schema.
    Raises ValidationError with detailed messages if invalid.
    """
    return StructuredItinerary.model_validate(data)


def itinerary_to_dict(itinerary: StructuredItinerary) -> dict:
    """Convert StructuredItinerary to dictionary (for storage)."""
    return itinerary.model_dump()


def dict_to_itinerary(data: dict) -> StructuredItinerary:
    """Convert dictionary to StructuredItinerary (from storage)."""
    return StructuredItinerary.model_validate(data)
