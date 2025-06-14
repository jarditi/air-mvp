"""
Calendar-Based Contact Extraction Service

This service implements Task 2.5.2: Calendar-based contact extraction (Priority 1).
It extracts high-quality contact information from calendar events and integrates
with the contact scoring system to evaluate relationship strength.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from lib.calendar_client import CalendarClient, CalendarEvent, CalendarSyncResult
from lib.google_cloud_config import google_cloud_manager
from models.orm.contact import Contact
from models.orm.user import User
from models.orm.integration import Integration
from services.contact_scoring import ContactScoringService, ScoringWeights
from services.integration_service import IntegrationService
from calendar_config import calendar_config

logger = logging.getLogger(__name__)


class CalendarContactExtractionService:
    """
    Service for extracting contacts from calendar events with intelligent scoring
    and deduplication capabilities.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the calendar contact extraction service
        
        Args:
            db: Database session
        """
        self.db = db
        self.integration_service = IntegrationService(db)
        self.contact_scoring_service = ContactScoringService()
    
    async def extract_contacts_from_calendar(
        self,
        user_id: str,
        days_back: Optional[int] = None,
        days_forward: Optional[int] = None,
        calendar_ids: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Extract contacts from user's calendar events
        
        Args:
            user_id: User ID
            days_back: Days back to sync (defaults to config)
            days_forward: Days forward to sync (defaults to config)
            calendar_ids: Specific calendar IDs to sync (defaults to all)
            force_refresh: Force refresh of all contacts
            
        Returns:
            Extraction results with statistics
        """
        try:
            # Get user and calendar integration
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            calendar_integration = self.integration_service.get_user_integration(
                user_id=user_id,
                provider="google_calendar"
            )
            
            if not calendar_integration or not calendar_integration.is_active:
                raise ValueError("Google Calendar integration not found or inactive")
            
            # Initialize calendar client with user's credentials
            credentials = self.integration_service.get_credentials(calendar_integration)
            calendar_client = CalendarClient(credentials)
            
            # Set sync time window
            sync_days_back = days_back or calendar_config.sync_days_back
            sync_days_forward = days_forward or calendar_config.sync_days_forward
            
            time_min = datetime.now(timezone.utc) - timedelta(days=sync_days_back)
            time_max = datetime.now(timezone.utc) + timedelta(days=sync_days_forward)
            
            # Fetch calendar events
            logger.info(f"Fetching calendar events for user {user_id} from {time_min} to {time_max}")
            
            sync_result = await calendar_client.fetch_all_events(
                calendar_ids=calendar_ids,
                time_min=time_min,
                time_max=time_max,
                max_results_per_calendar=calendar_config.max_results
            )
            
            if sync_result.errors:
                logger.warning(f"Calendar sync errors: {sync_result.errors}")
            
            # Extract contacts from events
            extracted_contacts = await calendar_client.extract_contacts_from_events(
                events=sync_result.events,
                user_email=user.email
            )
            
            # Process and score contacts
            processing_result = await self._process_extracted_contacts(
                user=user,
                extracted_contacts=extracted_contacts,
                force_refresh=force_refresh
            )
            
            return {
                "success": True,
                "user_id": user_id,
                "sync_result": {
                    "calendars_fetched": sync_result.calendars_fetched,
                    "events_fetched": sync_result.events_fetched,
                    "events_processed": sync_result.events_processed,
                    "sync_errors": sync_result.errors
                },
                "extraction_result": {
                    "contacts_extracted": len(extracted_contacts),
                    "contacts_created": processing_result["contacts_created"],
                    "contacts_updated": processing_result["contacts_updated"],
                    "contacts_skipped": processing_result["contacts_skipped"],
                    "high_quality_contacts": processing_result["high_quality_contacts"],
                    "processing_errors": processing_result["errors"]
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Calendar contact extraction failed for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _process_extracted_contacts(
        self,
        user: User,
        extracted_contacts: List[Dict[str, Any]],
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Process extracted contacts with scoring and deduplication
        
        Args:
            user: User object
            extracted_contacts: List of extracted contact data
            force_refresh: Force refresh of existing contacts
            
        Returns:
            Processing results with statistics
        """
        contacts_created = 0
        contacts_updated = 0
        contacts_skipped = 0
        high_quality_contacts = 0
        errors = []
        
        try:
            for contact_data in extracted_contacts:
                try:
                    # Check if contact already exists
                    existing_contact = self._find_existing_contact(user.id, contact_data)
                    
                    if existing_contact and not force_refresh:
                        # Update existing contact with new calendar data
                        updated = await self._update_existing_contact(
                            existing_contact, contact_data
                        )
                        if updated:
                            contacts_updated += 1
                        else:
                            contacts_skipped += 1
                    else:
                        # Create new contact or refresh existing
                        contact = await self._create_or_refresh_contact(
                            user, contact_data, existing_contact
                        )
                        
                        if existing_contact:
                            contacts_updated += 1
                        else:
                            contacts_created += 1
                        
                        # Check if it's a high-quality contact
                        if contact.relationship_strength >= 0.6:  # Strong Network tier
                            high_quality_contacts += 1
                
                except Exception as e:
                    error_msg = f"Failed to process contact {contact_data.get('email', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Commit all changes
            self.db.commit()
            
            logger.info(f"Contact processing complete: {contacts_created} created, "
                       f"{contacts_updated} updated, {contacts_skipped} skipped, "
                       f"{high_quality_contacts} high-quality")
            
            return {
                "contacts_created": contacts_created,
                "contacts_updated": contacts_updated,
                "contacts_skipped": contacts_skipped,
                "high_quality_contacts": high_quality_contacts,
                "errors": errors
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Contact processing failed: {e}")
            raise
    
    def _find_existing_contact(self, user_id: str, contact_data: Dict[str, Any]) -> Optional[Contact]:
        """
        Find existing contact by email or name matching
        
        Args:
            user_id: User ID
            contact_data: Contact data dictionary
            
        Returns:
            Existing contact or None
        """
        email = contact_data.get('email', '').lower().strip()
        name = contact_data.get('name', '').strip()
        
        if not email:
            return None
        
        # Primary match by email
        contact = self.db.query(Contact).filter(
            and_(
                Contact.user_id == user_id,
                Contact.email.ilike(email)
            )
        ).first()
        
        if contact:
            return contact
        
        # Secondary match by name if email not found
        if name and len(name) > 2:
            contact = self.db.query(Contact).filter(
                and_(
                    Contact.user_id == user_id,
                    or_(
                        Contact.full_name.ilike(f"%{name}%"),
                        Contact.first_name.ilike(f"%{name}%")
                    )
                )
            ).first()
        
        return contact
    
    async def _update_existing_contact(
        self,
        contact: Contact,
        contact_data: Dict[str, Any]
    ) -> bool:
        """
        Update existing contact with new calendar data
        
        Args:
            contact: Existing contact
            contact_data: New contact data from calendar
            
        Returns:
            True if contact was updated
        """
        updated = False
        
        try:
            # Update last interaction if newer
            last_interaction = contact_data.get('last_interaction')
            if last_interaction and (not contact.last_interaction_at or 
                                   last_interaction > contact.last_interaction_at):
                contact.last_interaction_at = last_interaction
                updated = True
            
            # Update relationship strength if higher
            new_strength = contact_data.get('relationship_strength', 0.0)
            if new_strength > (contact.relationship_strength or 0.0):
                contact.relationship_strength = new_strength
                updated = True
            
            # Update name if missing or more complete
            new_name = contact_data.get('name', '').strip()
            if new_name and (not contact.full_name or len(new_name) > len(contact.full_name or '')):
                contact.full_name = new_name
                # Try to split name
                name_parts = new_name.split(' ', 1)
                if len(name_parts) >= 1 and not contact.first_name:
                    contact.first_name = name_parts[0]
                if len(name_parts) >= 2 and not contact.last_name:
                    contact.last_name = name_parts[1]
                updated = True
            
            # Update source if not already calendar
            if contact.contact_source != 'calendar':
                contact.contact_source = 'calendar'
                updated = True
            
            if updated:
                contact.updated_at = datetime.now(timezone.utc)
                logger.debug(f"Updated existing contact: {contact.email}")
            
            return updated
            
        except Exception as e:
            logger.error(f"Failed to update contact {contact.email}: {e}")
            return False
    
    async def _create_or_refresh_contact(
        self,
        user: User,
        contact_data: Dict[str, Any],
        existing_contact: Optional[Contact] = None
    ) -> Contact:
        """
        Create new contact or refresh existing contact with calendar data
        
        Args:
            user: User object
            contact_data: Contact data from calendar
            existing_contact: Existing contact to refresh (optional)
            
        Returns:
            Created or updated contact
        """
        try:
            # Use existing contact or create new one
            contact = existing_contact or Contact()
            
            # Basic information
            contact.user_id = user.id
            contact.email = contact_data.get('email', '').lower().strip()
            
            # Name handling
            name = contact_data.get('name', '').strip()
            if name:
                contact.full_name = name
                name_parts = name.split(' ', 1)
                if len(name_parts) >= 1:
                    contact.first_name = name_parts[0]
                if len(name_parts) >= 2:
                    contact.last_name = name_parts[1]
            
            # Relationship metrics from calendar analysis
            contact.relationship_strength = contact_data.get('relationship_strength', 0.0)
            contact.last_interaction_at = contact_data.get('last_interaction')
            
            # Determine interaction frequency based on meeting count and timespan
            interaction_count = contact_data.get('interaction_count', 0)
            first_interaction = contact_data.get('first_interaction')
            last_interaction = contact_data.get('last_interaction')
            
            if first_interaction and last_interaction and interaction_count > 1:
                days_span = (last_interaction - first_interaction).days
                if days_span > 0:
                    meetings_per_month = (interaction_count * 30) / days_span
                    if meetings_per_month >= 4:
                        contact.interaction_frequency = 'weekly'
                    elif meetings_per_month >= 1:
                        contact.interaction_frequency = 'monthly'
                    elif meetings_per_month >= 0.25:
                        contact.interaction_frequency = 'quarterly'
                    else:
                        contact.interaction_frequency = 'rarely'
                else:
                    contact.interaction_frequency = 'rarely'
            else:
                contact.interaction_frequency = 'rarely'
            
            # Metadata
            contact.contact_source = 'calendar'
            contact.is_archived = False
            
            # Add calendar-specific notes
            metadata = contact_data.get('metadata', {})
            meeting_count = contact_data.get('meeting_count', 0)
            meeting_types = metadata.get('meeting_types', [])
            locations = metadata.get('locations', [])
            
            notes_parts = []
            if meeting_count > 0:
                notes_parts.append(f"Met {meeting_count} times via calendar")
            if meeting_types:
                notes_parts.append(f"Meeting types: {', '.join(meeting_types)}")
            if locations:
                top_locations = list(locations)[:3]  # Top 3 locations
                notes_parts.append(f"Common locations: {', '.join(top_locations)}")
            
            if notes_parts:
                calendar_notes = "; ".join(notes_parts)
                if contact.notes:
                    contact.notes = f"{contact.notes}\n\nCalendar: {calendar_notes}"
                else:
                    contact.notes = f"Calendar: {calendar_notes}"
            
            # Set timestamps
            now = datetime.now(timezone.utc)
            if not existing_contact:
                contact.created_at = now
            contact.updated_at = now
            
            # Add to database if new
            if not existing_contact:
                self.db.add(contact)
                self.db.flush()  # Get the ID
                logger.info(f"Created new contact from calendar: {contact.email}")
            else:
                logger.info(f"Refreshed existing contact from calendar: {contact.email}")
            
            return contact
            
        except Exception as e:
            logger.error(f"Failed to create/refresh contact: {e}")
            raise
    
    async def get_calendar_contact_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get statistics about calendar-based contacts for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Statistics about calendar contacts
        """
        try:
            # Get all calendar contacts
            calendar_contacts = self.db.query(Contact).filter(
                and_(
                    Contact.user_id == user_id,
                    Contact.contact_source == 'calendar'
                )
            ).all()
            
            if not calendar_contacts:
                return {
                    "total_contacts": 0,
                    "by_strength_tier": {},
                    "by_interaction_frequency": {},
                    "recent_interactions": 0,
                    "avg_relationship_strength": 0.0
                }
            
            # Calculate statistics
            total_contacts = len(calendar_contacts)
            
            # Group by relationship strength tiers
            strength_tiers = {
                "inner_circle": 0,      # 0.8-1.0
                "strong_network": 0,    # 0.6-0.8
                "active_network": 0,    # 0.4-0.6
                "peripheral": 0,        # 0.2-0.4
                "dormant": 0           # 0.0-0.2
            }
            
            frequency_counts = {}
            recent_interactions = 0
            total_strength = 0.0
            
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            
            for contact in calendar_contacts:
                # Strength tiers
                strength = contact.relationship_strength or 0.0
                total_strength += strength
                
                if strength >= 0.8:
                    strength_tiers["inner_circle"] += 1
                elif strength >= 0.6:
                    strength_tiers["strong_network"] += 1
                elif strength >= 0.4:
                    strength_tiers["active_network"] += 1
                elif strength >= 0.2:
                    strength_tiers["peripheral"] += 1
                else:
                    strength_tiers["dormant"] += 1
                
                # Interaction frequency
                freq = contact.interaction_frequency or 'rarely'
                frequency_counts[freq] = frequency_counts.get(freq, 0) + 1
                
                # Recent interactions
                if (contact.last_interaction_at and 
                    contact.last_interaction_at > thirty_days_ago):
                    recent_interactions += 1
            
            avg_strength = total_strength / total_contacts if total_contacts > 0 else 0.0
            
            return {
                "total_contacts": total_contacts,
                "by_strength_tier": strength_tiers,
                "by_interaction_frequency": frequency_counts,
                "recent_interactions": recent_interactions,
                "avg_relationship_strength": round(avg_strength, 3),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get calendar contact stats for user {user_id}: {e}")
            raise
    
    async def suggest_calendar_contacts_to_reconnect(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Suggest calendar contacts that might need reconnection
        
        Args:
            user_id: User ID
            limit: Maximum number of suggestions
            
        Returns:
            List of contact suggestions with reasons
        """
        try:
            # Find contacts that haven't been contacted recently but have good relationship strength
            ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
            
            stale_contacts = self.db.query(Contact).filter(
                and_(
                    Contact.user_id == user_id,
                    Contact.contact_source == 'calendar',
                    Contact.relationship_strength >= 0.4,  # Active network or better
                    Contact.is_archived == False,
                    or_(
                        Contact.last_interaction_at < ninety_days_ago,
                        Contact.last_interaction_at.is_(None)
                    )
                )
            ).order_by(
                Contact.relationship_strength.desc(),
                Contact.last_interaction_at.desc()
            ).limit(limit).all()
            
            suggestions = []
            for contact in stale_contacts:
                days_since_contact = None
                if contact.last_interaction_at:
                    days_since_contact = (datetime.now(timezone.utc) - contact.last_interaction_at).days
                
                reason = "Strong relationship that's gone quiet"
                if contact.relationship_strength >= 0.8:
                    reason = "Inner circle contact - high priority reconnection"
                elif contact.relationship_strength >= 0.6:
                    reason = "Strong network contact worth reconnecting with"
                
                suggestions.append({
                    "contact_id": str(contact.id),
                    "name": contact.full_name or contact.email,
                    "email": contact.email,
                    "relationship_strength": float(contact.relationship_strength or 0.0),
                    "days_since_contact": days_since_contact,
                    "last_interaction": contact.last_interaction_at.isoformat() if contact.last_interaction_at else None,
                    "interaction_frequency": contact.interaction_frequency,
                    "reason": reason
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to get reconnection suggestions for user {user_id}: {e}")
            raise 