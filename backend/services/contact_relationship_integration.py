"""
Contact Relationship Integration Service

This service ensures that contact scoring results are properly integrated
with the relationship_strength field in the Contact model.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from .contact_scoring import ContactScoringService
from models.orm.contact import Contact
from models.orm.interaction import Interaction

logger = logging.getLogger(__name__)


class ContactRelationshipIntegrationService:
    """Service to integrate contact scoring with relationship strength fields"""
    
    def __init__(self):
        self.scoring_service = ContactScoringService()
    
    async def update_contact_relationship_strength(
        self,
        db: Session,
        user_id: str,
        contact_id: str
    ) -> Dict[str, Any]:
        """Update relationship strength for a specific contact"""
        try:
            # Get contact and interactions
            contact = db.query(Contact).filter(
                Contact.id == contact_id,
                Contact.user_id == user_id
            ).first()
            
            if not contact:
                raise ValueError(f"Contact {contact_id} not found")
            
            interactions = db.query(Interaction).filter(
                Interaction.contact_id == contact_id,
                Interaction.user_id == user_id
            ).all()
            
            # Prepare data for scoring
            contact_data = {
                "id": str(contact.id),
                "full_name": contact.full_name,
                "email": contact.email,
                "company": contact.company,
                "job_title": contact.job_title
            }
            
            interactions_data = []
            for interaction in interactions:
                interactions_data.append({
                    "interaction_type": interaction.interaction_type,
                    "direction": interaction.direction,
                    "interaction_date": interaction.interaction_date,
                    "content": interaction.content or "",
                    "duration_minutes": interaction.duration_minutes
                })
            
            # Calculate relationship strength
            scoring_result = await self.scoring_service.score_contact(
                contact_data, interactions_data
            )
            
            # Update contact
            contact.relationship_strength = scoring_result["overall_score"]
            if interactions:
                contact.last_interaction_at = max(i.interaction_date for i in interactions)
            
            # Update interaction frequency
            frequency_per_month = scoring_result["metrics"]["interaction_frequency_per_month"]
            if frequency_per_month >= 4:
                contact.interaction_frequency = "weekly"
            elif frequency_per_month >= 1:
                contact.interaction_frequency = "monthly"
            elif frequency_per_month >= 0.25:
                contact.interaction_frequency = "quarterly"
            else:
                contact.interaction_frequency = "rarely"
            
            db.commit()
            
            return {
                "contact_id": str(contact.id),
                "relationship_strength": float(contact.relationship_strength),
                "tier": scoring_result["tier"],
                "interaction_frequency": contact.interaction_frequency,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to update relationship strength: {e}")
            db.rollback()
            raise
    
    async def update_all_contacts_relationship_strength(
        self,
        db: Session,
        user_id: str
    ) -> Dict[str, Any]:
        """Update relationship strength for all user contacts"""
        try:
            contacts = db.query(Contact).filter(
                Contact.user_id == user_id,
                Contact.is_archived == False
            ).all()
            
            updated_count = 0
            failed_count = 0
            
            for contact in contacts:
                try:
                    await self.update_contact_relationship_strength(
                        db, user_id, str(contact.id)
                    )
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Failed to update contact {contact.id}: {e}")
                    failed_count += 1
            
            return {
                "total_contacts": len(contacts),
                "updated_count": updated_count,
                "failed_count": failed_count,
                "success_rate": updated_count / len(contacts) if contacts else 0.0,
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to update all relationship strengths: {e}")
            raise
    
    async def get_relationship_strength_stats(
        self,
        db: Session,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get relationship strength statistics for a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Relationship strength statistics
        """
        try:
            contacts = db.query(Contact).filter(
                Contact.user_id == user_id,
                Contact.is_archived == False,
                Contact.relationship_strength.isnot(None)
            ).all()
            
            if not contacts:
                return {
                    "total_contacts": 0,
                    "average_strength": 0.0,
                    "tier_distribution": {},
                    "strength_distribution": {},
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            
            # Calculate statistics
            strengths = [float(c.relationship_strength) for c in contacts]
            avg_strength = sum(strengths) / len(strengths)
            
            # Tier distribution
            tier_counts = {
                "inner_circle": 0,
                "strong_network": 0,
                "active_network": 0,
                "peripheral": 0,
                "dormant": 0
            }
            
            # Strength distribution
            strength_ranges = {
                "0.8-1.0": 0,
                "0.6-0.8": 0,
                "0.4-0.6": 0,
                "0.2-0.4": 0,
                "0.0-0.2": 0
            }
            
            for contact in contacts:
                strength = float(contact.relationship_strength)
                
                # Tier classification
                if strength >= 0.8:
                    tier_counts["inner_circle"] += 1
                elif strength >= 0.6:
                    tier_counts["strong_network"] += 1
                elif strength >= 0.4:
                    tier_counts["active_network"] += 1
                elif strength >= 0.2:
                    tier_counts["peripheral"] += 1
                else:
                    tier_counts["dormant"] += 1
                
                # Strength ranges
                if strength >= 0.8:
                    strength_ranges["0.8-1.0"] += 1
                elif strength >= 0.6:
                    strength_ranges["0.6-0.8"] += 1
                elif strength >= 0.4:
                    strength_ranges["0.4-0.6"] += 1
                elif strength >= 0.2:
                    strength_ranges["0.2-0.4"] += 1
                else:
                    strength_ranges["0.0-0.2"] += 1
            
            return {
                "total_contacts": len(contacts),
                "average_strength": round(avg_strength, 3),
                "median_strength": round(sorted(strengths)[len(strengths)//2], 3),
                "max_strength": round(max(strengths), 3),
                "min_strength": round(min(strengths), 3),
                "tier_distribution": tier_counts,
                "strength_distribution": strength_ranges,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get relationship strength stats for user {user_id}: {e}")
            raise 