"""
Calendar API Configuration

This module contains configuration settings specific to Google Calendar API integration.
"""

import os
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta


@dataclass
class CalendarConfig:
    """Calendar API configuration settings"""
    
    # API Limits and Pagination
    max_results: int = 250  # Maximum events per API call
    max_calendars: int = 50  # Maximum calendars to sync
    
    # Sync Time Windows
    sync_days_back: int = 30  # How many days back to sync
    sync_days_forward: int = 90  # How many days forward to sync
    
    # Rate Limiting
    requests_per_second: float = 10.0  # Google Calendar API rate limit
    requests_per_minute: int = 600  # Google Calendar API rate limit
    requests_per_day: int = 1000000  # Google Calendar API rate limit
    
    # Sync Behavior
    incremental_sync: bool = True  # Use incremental sync when possible
    sync_deleted_events: bool = True  # Include deleted events in sync
    sync_private_events: bool = False  # Sync private events (requires additional permissions)
    
    # Event Filtering
    exclude_all_day_events: bool = False  # Exclude all-day events
    exclude_recurring_instances: bool = False  # Exclude recurring event instances
    min_event_duration_minutes: int = 0  # Minimum event duration to include
    
    # Contact Extraction Settings
    extract_attendees: bool = True  # Extract attendee information
    extract_organizers: bool = True  # Extract organizer information
    min_attendees_for_contact: int = 1  # Minimum attendees to consider for contact extraction
    exclude_self_meetings: bool = True  # Exclude meetings with only the user
    
    # Privacy and Security
    anonymize_private_events: bool = True  # Anonymize private event details
    store_event_content: bool = True  # Store event descriptions and content
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.sync_days_back < 0:
            raise ValueError("sync_days_back must be non-negative")
        if self.sync_days_forward < 0:
            raise ValueError("sync_days_forward must be non-negative")
        if self.max_results <= 0:
            raise ValueError("max_results must be positive")
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
    
    @property
    def sync_start_date(self) -> datetime:
        """Get the start date for calendar sync"""
        return datetime.now() - timedelta(days=self.sync_days_back)
    
    @property
    def sync_end_date(self) -> datetime:
        """Get the end date for calendar sync"""
        return datetime.now() + timedelta(days=self.sync_days_forward)
    
    @property
    def rate_limit_delay(self) -> float:
        """Get the delay between requests for rate limiting"""
        return 1.0 / self.requests_per_second
    
    def get_calendar_query_params(self) -> Dict[str, Any]:
        """Get query parameters for Calendar API calls"""
        return {
            'maxResults': self.max_results,
            'singleEvents': True,  # Expand recurring events
            'orderBy': 'startTime',
            'timeMin': self.sync_start_date.isoformat() + 'Z',
            'timeMax': self.sync_end_date.isoformat() + 'Z',
            'showDeleted': self.sync_deleted_events
        }
    
    def should_include_event(self, event: Dict[str, Any]) -> bool:
        """
        Determine if an event should be included based on configuration
        
        Args:
            event: Calendar event data from Google API
            
        Returns:
            True if event should be included
        """
        # Check all-day events
        if self.exclude_all_day_events and event.get('start', {}).get('date'):
            return False
        
        # Check recurring instances
        if self.exclude_recurring_instances and event.get('recurringEventId'):
            return False
        
        # Check event duration
        if self.min_event_duration_minutes > 0:
            start = event.get('start', {})
            end = event.get('end', {})
            
            if start.get('dateTime') and end.get('dateTime'):
                start_time = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
                duration_minutes = (end_time - start_time).total_seconds() / 60
                
                if duration_minutes < self.min_event_duration_minutes:
                    return False
        
        return True
    
    def should_extract_contacts_from_event(self, event: Dict[str, Any], user_email: str) -> bool:
        """
        Determine if contacts should be extracted from an event
        
        Args:
            event: Calendar event data from Google API
            user_email: User's email address
            
        Returns:
            True if contacts should be extracted
        """
        attendees = event.get('attendees', [])
        
        # Check minimum attendees
        if len(attendees) < self.min_attendees_for_contact:
            return False
        
        # Check if it's a self-meeting
        if self.exclude_self_meetings:
            other_attendees = [a for a in attendees if a.get('email', '').lower() != user_email.lower()]
            if len(other_attendees) == 0:
                return False
        
        return True


def load_calendar_config() -> CalendarConfig:
    """
    Load calendar configuration from environment variables
    
    Returns:
        Calendar configuration instance
    """
    return CalendarConfig(
        max_results=int(os.getenv('CALENDAR_MAX_RESULTS', '250')),
        max_calendars=int(os.getenv('CALENDAR_MAX_CALENDARS', '50')),
        sync_days_back=int(os.getenv('CALENDAR_SYNC_DAYS_BACK', '30')),
        sync_days_forward=int(os.getenv('CALENDAR_SYNC_DAYS_FORWARD', '90')),
        requests_per_second=float(os.getenv('CALENDAR_REQUESTS_PER_SECOND', '10.0')),
        requests_per_minute=int(os.getenv('CALENDAR_REQUESTS_PER_MINUTE', '600')),
        requests_per_day=int(os.getenv('CALENDAR_REQUESTS_PER_DAY', '1000000')),
        incremental_sync=os.getenv('CALENDAR_INCREMENTAL_SYNC', 'true').lower() == 'true',
        sync_deleted_events=os.getenv('CALENDAR_SYNC_DELETED_EVENTS', 'true').lower() == 'true',
        sync_private_events=os.getenv('CALENDAR_SYNC_PRIVATE_EVENTS', 'false').lower() == 'true',
        exclude_all_day_events=os.getenv('CALENDAR_EXCLUDE_ALL_DAY_EVENTS', 'false').lower() == 'true',
        exclude_recurring_instances=os.getenv('CALENDAR_EXCLUDE_RECURRING_INSTANCES', 'false').lower() == 'true',
        min_event_duration_minutes=int(os.getenv('CALENDAR_MIN_EVENT_DURATION_MINUTES', '0')),
        extract_attendees=os.getenv('CALENDAR_EXTRACT_ATTENDEES', 'true').lower() == 'true',
        extract_organizers=os.getenv('CALENDAR_EXTRACT_ORGANIZERS', 'true').lower() == 'true',
        min_attendees_for_contact=int(os.getenv('CALENDAR_MIN_ATTENDEES_FOR_CONTACT', '1')),
        exclude_self_meetings=os.getenv('CALENDAR_EXCLUDE_SELF_MEETINGS', 'true').lower() == 'true',
        anonymize_private_events=os.getenv('CALENDAR_ANONYMIZE_PRIVATE_EVENTS', 'true').lower() == 'true',
        store_event_content=os.getenv('CALENDAR_STORE_EVENT_CONTENT', 'true').lower() == 'true'
    )


# Global configuration instance
calendar_config = load_calendar_config() 