"""
Itinerary Renderer - Converts structured components to user-friendly markdown.
Uses Jinja2 templates for consistent, maintainable rendering.
"""

from __future__ import annotations
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
from core.component_schemas import StructuredItinerary

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class ItineraryRenderer:
    """Renders structured itineraries to markdown using Jinja2."""

    def __init__(self):
        """Initialize Jinja2 environment."""
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,  # We're generating markdown, not HTML
            trim_blocks=True,
            lstrip_blocks=True
        )
        logger.debug(f"Initialized ItineraryRenderer with templates from {TEMPLATE_DIR}")

    def render(self, itinerary: StructuredItinerary) -> str:
        """
        Render a structured itinerary to markdown.

        Args:
            itinerary: Validated StructuredItinerary object

        Returns:
            Markdown-formatted itinerary string
        """
        try:
            template = self.env.get_template("itinerary.jinja2")

            # Convert Pydantic model to dict for template
            context = itinerary.model_dump()

            rendered = template.render(**context)
            logger.debug(f"Rendered itinerary: {len(rendered)} characters")
            return rendered

        except Exception as exc:
            logger.exception("Failed to render itinerary")
            # Return a simple fallback
            return self._render_fallback(itinerary)

    def _render_fallback(self, itinerary: StructuredItinerary) -> str:
        """Simple fallback rendering if template fails."""
        meta = itinerary.metadata
        output = f"# Your {meta.destination} Trip\n\n"
        output += f"**Duration**: {meta.duration_days} days\n"
        output += f"**Dates**: {meta.departure_date} to {meta.return_date}\n\n"

        output += "## Transport Options\n"
        for i, transport in enumerate(itinerary.transport_options, 1):
            recommended = " (Recommended)" if transport.recommended else ""
            output += f"{i}. **{transport.mode.title()}**{recommended}\n"

        output += "\n## Accommodation Options\n"
        for i, hotel in enumerate(itinerary.accommodation_options, 1):
            output += f"{i}. **{hotel.name}** - ${hotel.price_per_night}/night\n"

        output += "\n## Daily Schedule\n"
        for day in itinerary.days:
            output += f"\n### Day {day.day_number} - {day.theme}\n"

        return output


# Global renderer instance
_renderer = None


def get_renderer() -> ItineraryRenderer:
    """Get or create the global renderer instance."""
    global _renderer
    if _renderer is None:
        _renderer = ItineraryRenderer()
    return _renderer


def render_itinerary(itinerary: StructuredItinerary) -> str:
    """
    Convenience function to render an itinerary.

    Args:
        itinerary: Validated StructuredItinerary

    Returns:
        Markdown string
    """
    renderer = get_renderer()
    return renderer.render(itinerary)
