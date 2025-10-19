"""
API client for communicating with the Travel Planner backend.
Handles requests to Docker-based backend service.
"""

import requests
import os
from typing import Dict, Any, Optional


class TravelPlannerClient:
    """Client for interacting with the Travel Planner backend API."""

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the API client.

        Args:
            base_url: Backend API URL (defaults to env var or localhost:8000)
        """
        self.base_url = base_url or os.getenv(
            "TRAVEL_PLANNER_API_URL",
            "http://localhost:8000"
        )
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message to the travel planner.

        Args:
            message: User message
            conversation_id: Optional conversation ID for multi-turn

        Returns:
            Response containing AI message and optional itinerary

        Raises:
            requests.RequestException: If API call fails
        """
        payload = {
            "message": message,
            "conversation_id": conversation_id
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=600  # 10 minutes for research-heavy requests
            )
            response.raise_for_status()
            return response.json()

        except requests.Timeout:
            return {
                "message": "The request timed out after 10 minutes. The AI agents may be experiencing issues. Please try again.",
                "error": "timeout"
            }
        except requests.ConnectionError:
            return {
                "message": "Cannot connect to the backend. Please ensure Docker is running.",
                "error": "connection"
            }
        except requests.RequestException as e:
            return {
                "message": f"Error: {str(e)}",
                "error": "request_failed"
            }

    def select_hotel(
        self,
        conversation_id: str,
        hotel_index: int
    ) -> Dict[str, Any]:
        """
        Select a hotel from the options.

        Args:
            conversation_id: Current conversation ID
            hotel_index: Index of selected hotel (1-3)

        Returns:
            Updated itinerary response
        """
        payload = {
            "conversation_id": conversation_id,
            "action": "select_hotel",
            "hotel_index": hotel_index
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/refine",
                json=payload,
                timeout=120  # 2 minutes for refinement requests
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            return {
                "message": f"Error selecting hotel: {str(e)}",
                "error": "request_failed"
            }

    def swap_activity(
        self,
        conversation_id: str,
        day_number: int,
        time_slot: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request to swap an activity.

        Args:
            conversation_id: Current conversation ID
            day_number: Day number (1-7)
            time_slot: Time slot ("morning", "afternoon", "evening")
            reason: Optional reason for swapping

        Returns:
            Updated itinerary with new activity
        """
        payload = {
            "conversation_id": conversation_id,
            "action": "swap_activity",
            "day_number": day_number,
            "time_slot": time_slot,
            "reason": reason
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/refine",
                json=payload,
                timeout=120  # 2 minutes for refinement requests
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            return {
                "message": f"Error swapping activity: {str(e)}",
                "error": "request_failed"
            }

    def health_check(self) -> bool:
        """
        Check if backend is healthy.

        Returns:
            True if backend is accessible, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
