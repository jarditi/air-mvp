"""
Interaction Timeline Service - Simplified

This service implements Task 3.2.3: Build interaction timeline assembly with source prioritization.
Refactored to focus on the core value: tracking days since last interaction for actionable
relationship management.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from models.orm.interaction import Interaction
from models.orm.contact import Contact
from models.orm.user import User

logger = logging.getLogger(__name__)


class InteractionSource(Enum):
    """Interaction source types with priority levels"""
    MANUAL = ("manual", 1.0)
    CALENDAR = ("calendar", 0.9)
    EMAIL = ("email", 0.8)
    LINKEDIN = ("linkedin", 0.7)
    AUTOMATED = ("automated", 0.3)
    
    def __init__(self, source_name: str, trust_score: float):
        self.source_name = source_name
        self.trust_score = trust_score


@dataclass
class ContactLastInteraction:
    """Contact with last interaction details"""
    contact_id: str
    contact_name: str
    contact_email: str
    company: Optional[str]
    days_since_last_interaction: int
    last_interaction_date: datetime
    last_interaction_type: str
    last_interaction_subject: Optional[str]
    relationship_strength: float
    total_interactions: int
    needs_attention: bool


class InteractionTimelineService:
    """
    Simplified service for tracking interaction recency and relationship health
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.source_priorities = {
            source.source_name: source.trust_score 
            for source in InteractionSource
        }
        self.attention_thresholds = {
            "high_priority": 14,    # Inner circle - 2 weeks
            "medium_priority": 30,  # Regular contacts - 1 month
            "low_priority": 90      # Occasional contacts - 3 months
        }
    
    async def get_contacts_by_last_interaction(
        self,
        user_id: str,
        limit: Optional[int] = None,
        needs_attention_only: bool = False,
        min_relationship_strength: float = 0.0
    ) -> List[ContactLastInteraction]:
        """Get contacts sorted by days since last interaction"""
        try:
            # Simple query to get contacts with last interaction
            contacts = self.db.query(Contact).filter(
                and_(
                    Contact.user_id == user_id,
                    Contact.is_archived == False,
                    Contact.relationship_strength >= min_relationship_strength
                )
            ).all()
            
            result_contacts = []
            now = datetime.now(timezone.utc)
            
            for contact in contacts:
                # Get last interaction for this contact
                last_interaction = self.db.query(Interaction).filter(
                    and_(
                        Interaction.user_id == user_id,
                        Interaction.contact_id == contact.id
                    )
                ).order_by(Interaction.interaction_date.desc()).first()
                
                if not last_interaction:
                    continue
                
                days_ago = (now - last_interaction.interaction_date).days
                needs_attention = self._needs_attention(days_ago, contact.relationship_strength or 0.0)
                
                if needs_attention_only and not needs_attention:
                    continue
                
                # Get total interaction count
                total_count = self.db.query(Interaction).filter(
                    and_(
                        Interaction.user_id == user_id,
                        Interaction.contact_id == contact.id
                    )
                ).count()
                
                contact_data = ContactLastInteraction(
                    contact_id=str(contact.id),
                    contact_name=contact.full_name or contact.email,
                    contact_email=contact.email,
                    company=contact.company,
                    days_since_last_interaction=days_ago,
                    last_interaction_date=last_interaction.interaction_date,
                    last_interaction_type=last_interaction.interaction_type,
                    last_interaction_subject=last_interaction.subject,
                    relationship_strength=float(contact.relationship_strength or 0.0),
                    total_interactions=total_count,
                    needs_attention=needs_attention
                )
                result_contacts.append(contact_data)
            
            # Sort by days since last interaction (descending - oldest first)
            result_contacts.sort(key=lambda x: x.days_since_last_interaction, reverse=True)
            
            if limit:
                result_contacts = result_contacts[:limit]
            
            return result_contacts
            
        except Exception as e:
            logger.error(f"Failed to get contacts by last interaction for user {user_id}: {e}")
            raise
    
    def _needs_attention(self, days_since_last: int, relationship_strength: float) -> bool:
        """Determine if a contact needs attention"""
        if relationship_strength >= 0.7:
            return days_since_last >= self.attention_thresholds["high_priority"]
        elif relationship_strength >= 0.4:
            return days_since_last >= self.attention_thresholds["medium_priority"]
        else:
            return days_since_last >= self.attention_thresholds["low_priority"]
    
    async def get_attention_dashboard(self, user_id: str) -> Dict[str, Any]:
        """Get dashboard showing contacts that need attention"""
        try:
            all_contacts = await self.get_contacts_by_last_interaction(user_id)
            
            needs_immediate_attention = []
            needs_attention_soon = []
            going_cold = []
            
            for contact in all_contacts:
                days = contact.days_since_last_interaction
                strength = contact.relationship_strength
                
                if days >= 90:
                    going_cold.append(contact)
                elif strength >= 0.6 and days >= 30:
                    needs_immediate_attention.append(contact)
                elif strength >= 0.6 and days >= 14:
                    needs_attention_soon.append(contact)
            
            total_contacts = len(all_contacts)
            active_contacts = len([c for c in all_contacts if c.days_since_last_interaction <= 7])
            dormant_contacts = len([c for c in all_contacts if c.days_since_last_interaction >= 90])
            
            return {
                "user_id": user_id,
                "total_contacts": total_contacts,
                "active_contacts": active_contacts,
                "dormant_contacts": dormant_contacts,
                "needs_immediate_attention": [c.__dict__ for c in needs_immediate_attention[:10]],
                "needs_attention_soon": [c.__dict__ for c in needs_attention_soon[:10]],
                "going_cold": [c.__dict__ for c in going_cold[:10]],
                "summary": {
                    "immediate_attention_count": len(needs_immediate_attention),
                    "attention_soon_count": len(needs_attention_soon),
                    "going_cold_count": len(going_cold)
                },
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get attention dashboard for user {user_id}: {e}")
            raise
