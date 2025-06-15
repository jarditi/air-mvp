"""
Contact Merging Service (Task 2.5.5)

Intelligent contact merging with data preservation, conflict resolution,
and audit trail for contact deduplication workflows.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.orm.contact import Contact
from models.orm.interaction import Interaction
from models.orm.interest import Interest
from models.orm.user import User
from services.contact_deduplication import DuplicateMatch, ContactDeduplicationService

logger = logging.getLogger(__name__)


class MergeStrategy(Enum):
    """Contact merge strategies"""
    TAKE_PRIMARY = "take_primary"           # Use primary contact's data
    TAKE_SECONDARY = "take_secondary"       # Use secondary contact's data
    TAKE_MOST_COMPLETE = "take_most_complete"  # Use most complete data
    TAKE_MOST_RECENT = "take_most_recent"   # Use most recent data
    CONCATENATE = "concatenate"             # Combine both values
    MANUAL_REVIEW = "manual_review"         # Requires manual decision


@dataclass
class MergeConflict:
    """Represents a conflict between two contact fields during merge"""
    field_name: str
    primary_value: Any
    secondary_value: Any
    recommended_strategy: MergeStrategy
    confidence: float
    reason: str


@dataclass
class MergeResult:
    """Result of a contact merge operation"""
    success: bool
    merged_contact_id: str
    removed_contact_id: str
    conflicts_resolved: List[MergeConflict]
    data_preserved: Dict[str, Any]
    interactions_merged: int
    interests_merged: int
    error_message: Optional[str] = None


@dataclass
class MergePreview:
    """Preview of what would happen in a merge operation"""
    primary_contact_id: str
    secondary_contact_id: str
    merged_data: Dict[str, Any]
    conflicts: List[MergeConflict]
    interactions_to_merge: int
    interests_to_merge: int
    estimated_data_loss: List[str]


class ContactMergingService:
    """
    Intelligent contact merging service with conflict resolution
    
    Features:
    - Smart field merging with multiple strategies
    - Conflict detection and resolution
    - Data preservation and audit trail
    - Interaction and interest merging
    - Rollback capability
    - Merge preview functionality
    """
    
    # Field merge strategies configuration
    FIELD_STRATEGIES = {
        # Identity fields - take most complete
        'email': MergeStrategy.TAKE_MOST_COMPLETE,
        'phone': MergeStrategy.TAKE_MOST_COMPLETE,
        'linkedin_url': MergeStrategy.TAKE_MOST_COMPLETE,
        
        # Name fields - take most complete or recent
        'full_name': MergeStrategy.TAKE_MOST_COMPLETE,
        'first_name': MergeStrategy.TAKE_MOST_COMPLETE,
        'last_name': MergeStrategy.TAKE_MOST_COMPLETE,
        
        # Professional fields - take most recent
        'company': MergeStrategy.TAKE_MOST_RECENT,
        'job_title': MergeStrategy.TAKE_MOST_RECENT,
        'location': MergeStrategy.TAKE_MOST_RECENT,
        
        # Relationship metrics - take highest/most recent
        'relationship_strength': MergeStrategy.TAKE_PRIMARY,  # Highest value
        'last_interaction_at': MergeStrategy.TAKE_MOST_RECENT,
        'interaction_frequency': MergeStrategy.TAKE_PRIMARY,
        
        # Metadata - combine or take primary
        'tags': MergeStrategy.CONCATENATE,
        'notes': MergeStrategy.CONCATENATE,
        'bio': MergeStrategy.TAKE_MOST_COMPLETE,
        'avatar_url': MergeStrategy.TAKE_MOST_COMPLETE,
        
        # Source tracking - take primary
        'contact_source': MergeStrategy.TAKE_PRIMARY,
        'is_archived': MergeStrategy.TAKE_PRIMARY,
    }
    
    def __init__(self, db: Session):
        """
        Initialize contact merging service
        
        Args:
            db: Database session
        """
        self.db = db
        self.dedup_service = ContactDeduplicationService(db)
    
    async def preview_merge(
        self,
        user_id: str,
        primary_contact_id: str,
        secondary_contact_id: str
    ) -> MergePreview:
        """
        Preview what would happen in a merge operation
        
        Args:
            user_id: User ID for security
            primary_contact_id: ID of contact to keep
            secondary_contact_id: ID of contact to merge and remove
            
        Returns:
            Preview of merge operation
        """
        try:
            # Get both contacts
            primary_contact = self._get_contact(user_id, primary_contact_id)
            secondary_contact = self._get_contact(user_id, secondary_contact_id)
            
            if not primary_contact or not secondary_contact:
                raise ValueError("One or both contacts not found")
            
            # Analyze merge conflicts
            conflicts = self._analyze_merge_conflicts(primary_contact, secondary_contact)
            
            # Generate merged data preview
            merged_data = self._generate_merged_data(primary_contact, secondary_contact, conflicts)
            
            # Count related data to merge
            interactions_count = self.db.query(Interaction).filter(
                Interaction.contact_id == secondary_contact_id
            ).count()
            
            interests_count = self.db.query(Interest).filter(
                Interest.contact_id == secondary_contact_id
            ).count()
            
            # Identify potential data loss
            estimated_data_loss = self._estimate_data_loss(primary_contact, secondary_contact, conflicts)
            
            return MergePreview(
                primary_contact_id=primary_contact_id,
                secondary_contact_id=secondary_contact_id,
                merged_data=merged_data,
                conflicts=conflicts,
                interactions_to_merge=interactions_count,
                interests_to_merge=interests_count,
                estimated_data_loss=estimated_data_loss
            )
            
        except Exception as e:
            logger.error(f"Error previewing merge: {e}")
            raise
    
    async def merge_contacts(
        self,
        user_id: str,
        primary_contact_id: str,
        secondary_contact_id: str,
        conflict_resolutions: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> MergeResult:
        """
        Merge two contacts with conflict resolution
        
        Args:
            user_id: User ID for security
            primary_contact_id: ID of contact to keep
            secondary_contact_id: ID of contact to merge and remove
            conflict_resolutions: Manual resolutions for conflicts
            dry_run: If True, don't actually perform the merge
            
        Returns:
            Result of merge operation
        """
        try:
            # Get both contacts
            primary_contact = self._get_contact(user_id, primary_contact_id)
            secondary_contact = self._get_contact(user_id, secondary_contact_id)
            
            if not primary_contact or not secondary_contact:
                raise ValueError("One or both contacts not found")
            
            # Analyze conflicts
            conflicts = self._analyze_merge_conflicts(primary_contact, secondary_contact)
            
            # Apply conflict resolutions
            if conflict_resolutions:
                conflicts = self._apply_conflict_resolutions(conflicts, conflict_resolutions)
            
            # Check for unresolved conflicts
            unresolved_conflicts = [c for c in conflicts if c.recommended_strategy == MergeStrategy.MANUAL_REVIEW]
            if unresolved_conflicts and not conflict_resolutions:
                return MergeResult(
                    success=False,
                    merged_contact_id=primary_contact_id,
                    removed_contact_id=secondary_contact_id,
                    conflicts_resolved=[],
                    data_preserved={},
                    interactions_merged=0,
                    interests_merged=0,
                    error_message=f"Manual review required for {len(unresolved_conflicts)} conflicts"
                )
            
            if dry_run:
                # Return preview without actually merging
                merged_data = self._generate_merged_data(primary_contact, secondary_contact, conflicts)
                return MergeResult(
                    success=True,
                    merged_contact_id=primary_contact_id,
                    removed_contact_id=secondary_contact_id,
                    conflicts_resolved=conflicts,
                    data_preserved=merged_data,
                    interactions_merged=0,
                    interests_merged=0
                )
            
            # Perform the actual merge
            return await self._execute_merge(
                primary_contact, secondary_contact, conflicts
            )
            
        except Exception as e:
            logger.error(f"Error merging contacts: {e}")
            return MergeResult(
                success=False,
                merged_contact_id=primary_contact_id,
                removed_contact_id=secondary_contact_id,
                conflicts_resolved=[],
                data_preserved={},
                interactions_merged=0,
                interests_merged=0,
                error_message=str(e)
            )
    
    async def auto_merge_high_confidence(
        self,
        user_id: str,
        max_merges: int = 50
    ) -> List[MergeResult]:
        """
        Automatically merge high-confidence duplicate contacts
        
        Args:
            user_id: User ID to process
            max_merges: Maximum number of merges to perform
            
        Returns:
            List of merge results
        """
        try:
            # Get auto-merge candidates
            candidates = await self.dedup_service.get_auto_merge_candidates(user_id)
            
            if not candidates:
                logger.info(f"No auto-merge candidates found for user {user_id}")
                return []
            
            # Limit the number of merges
            candidates = candidates[:max_merges]
            
            results = []
            for candidate in candidates:
                try:
                    # Determine primary contact (higher quality score)
                    primary_id, secondary_id = self._determine_merge_order(candidate)
                    
                    # Perform merge
                    result = await self.merge_contacts(
                        user_id=user_id,
                        primary_contact_id=primary_id,
                        secondary_contact_id=secondary_id,
                        dry_run=False
                    )
                    
                    results.append(result)
                    
                    if result.success:
                        logger.info(f"Auto-merged contacts {primary_id} and {secondary_id}")
                    else:
                        logger.warning(f"Auto-merge failed: {result.error_message}")
                
                except Exception as e:
                    logger.error(f"Error in auto-merge: {e}")
                    continue
            
            logger.info(f"Completed {len(results)} auto-merge operations")
            return results
            
        except Exception as e:
            logger.error(f"Error in auto-merge process: {e}")
            raise
    
    def _get_contact(self, user_id: str, contact_id: str) -> Optional[Contact]:
        """Get contact with security check"""
        return self.db.query(Contact).filter(
            and_(
                Contact.id == contact_id,
                Contact.user_id == user_id,
                Contact.is_archived == False
            )
        ).first()
    
    def _analyze_merge_conflicts(
        self,
        primary_contact: Contact,
        secondary_contact: Contact
    ) -> List[MergeConflict]:
        """Analyze potential conflicts between two contacts"""
        conflicts = []
        
        for field_name, strategy in self.FIELD_STRATEGIES.items():
            primary_value = getattr(primary_contact, field_name, None)
            secondary_value = getattr(secondary_contact, field_name, None)
            
            # Skip if values are the same or one is None
            if primary_value == secondary_value:
                continue
            if primary_value is None or secondary_value is None:
                continue
            
            # Special handling for different field types
            if field_name in ['tags', 'notes']:
                # These fields can be concatenated
                if primary_value and secondary_value:
                    conflicts.append(MergeConflict(
                        field_name=field_name,
                        primary_value=primary_value,
                        secondary_value=secondary_value,
                        recommended_strategy=MergeStrategy.CONCATENATE,
                        confidence=0.9,
                        reason="Values can be combined"
                    ))
            
            elif field_name == 'relationship_strength':
                # Take the higher value
                if float(primary_value or 0) != float(secondary_value or 0):
                    conflicts.append(MergeConflict(
                        field_name=field_name,
                        primary_value=primary_value,
                        secondary_value=secondary_value,
                        recommended_strategy=MergeStrategy.TAKE_PRIMARY if primary_value > secondary_value else MergeStrategy.TAKE_SECONDARY,
                        confidence=0.95,
                        reason="Take higher relationship strength"
                    ))
            
            else:
                # Determine strategy based on data completeness and recency
                if self._is_more_complete(primary_value, secondary_value):
                    recommended_strategy = MergeStrategy.TAKE_PRIMARY
                    confidence = 0.8
                    reason = "Primary value is more complete"
                elif self._is_more_complete(secondary_value, primary_value):
                    recommended_strategy = MergeStrategy.TAKE_SECONDARY
                    confidence = 0.8
                    reason = "Secondary value is more complete"
                else:
                    # Values are different but similar completeness
                    if strategy == MergeStrategy.TAKE_MOST_RECENT:
                        # Use updated_at to determine recency
                        if primary_contact.updated_at > secondary_contact.updated_at:
                            recommended_strategy = MergeStrategy.TAKE_PRIMARY
                            reason = "Primary contact is more recent"
                        else:
                            recommended_strategy = MergeStrategy.TAKE_SECONDARY
                            reason = "Secondary contact is more recent"
                        confidence = 0.7
                    else:
                        recommended_strategy = MergeStrategy.MANUAL_REVIEW
                        confidence = 0.5
                        reason = "Values differ significantly"
                
                conflicts.append(MergeConflict(
                    field_name=field_name,
                    primary_value=primary_value,
                    secondary_value=secondary_value,
                    recommended_strategy=recommended_strategy,
                    confidence=confidence,
                    reason=reason
                ))
        
        return conflicts
    
    def _is_more_complete(self, value_a: Any, value_b: Any) -> bool:
        """Determine if value_a is more complete than value_b"""
        if value_a is None:
            return False
        if value_b is None:
            return True
        
        # For strings, longer is generally more complete
        if isinstance(value_a, str) and isinstance(value_b, str):
            return len(value_a.strip()) > len(value_b.strip())
        
        return False
    
    def _generate_merged_data(
        self,
        primary_contact: Contact,
        secondary_contact: Contact,
        conflicts: List[MergeConflict]
    ) -> Dict[str, Any]:
        """Generate the merged data based on conflict resolutions"""
        merged_data = {}
        
        # Start with primary contact data
        for field_name in self.FIELD_STRATEGIES.keys():
            merged_data[field_name] = getattr(primary_contact, field_name, None)
        
        # Apply conflict resolutions
        for conflict in conflicts:
            if conflict.recommended_strategy == MergeStrategy.TAKE_SECONDARY:
                merged_data[conflict.field_name] = conflict.secondary_value
            elif conflict.recommended_strategy == MergeStrategy.CONCATENATE:
                if conflict.field_name == 'tags':
                    # Combine and deduplicate tags
                    primary_tags = conflict.primary_value or []
                    secondary_tags = conflict.secondary_value or []
                    merged_data[conflict.field_name] = list(set(primary_tags + secondary_tags))
                elif conflict.field_name == 'notes':
                    # Concatenate notes with source attribution
                    primary_notes = conflict.primary_value or ''
                    secondary_notes = conflict.secondary_value or ''
                    if primary_notes and secondary_notes:
                        merged_data[conflict.field_name] = f"{primary_notes}\n\n--- Merged from duplicate contact ---\n{secondary_notes}"
                    else:
                        merged_data[conflict.field_name] = primary_notes or secondary_notes
        
        return merged_data
    
    def _apply_conflict_resolutions(
        self,
        conflicts: List[MergeConflict],
        resolutions: Dict[str, Any]
    ) -> List[MergeConflict]:
        """Apply manual conflict resolutions"""
        for conflict in conflicts:
            if conflict.field_name in resolutions:
                resolution = resolutions[conflict.field_name]
                if resolution == 'primary':
                    conflict.recommended_strategy = MergeStrategy.TAKE_PRIMARY
                elif resolution == 'secondary':
                    conflict.recommended_strategy = MergeStrategy.TAKE_SECONDARY
                elif resolution == 'concatenate':
                    conflict.recommended_strategy = MergeStrategy.CONCATENATE
                conflict.confidence = 1.0  # Manual resolution is 100% confident
        
        return conflicts
    
    def _estimate_data_loss(
        self,
        primary_contact: Contact,
        secondary_contact: Contact,
        conflicts: List[MergeConflict]
    ) -> List[str]:
        """Estimate what data might be lost in the merge"""
        data_loss = []
        
        for conflict in conflicts:
            if conflict.recommended_strategy == MergeStrategy.TAKE_PRIMARY:
                if conflict.secondary_value:
                    data_loss.append(f"{conflict.field_name}: '{conflict.secondary_value}' will be lost")
            elif conflict.recommended_strategy == MergeStrategy.TAKE_SECONDARY:
                if conflict.primary_value:
                    data_loss.append(f"{conflict.field_name}: '{conflict.primary_value}' will be lost")
        
        return data_loss
    
    def _determine_merge_order(self, duplicate_match: DuplicateMatch) -> Tuple[str, str]:
        """Determine which contact should be primary in merge"""
        if duplicate_match.merge_priority == 'a_primary':
            return duplicate_match.contact_a_id, duplicate_match.contact_b_id
        elif duplicate_match.merge_priority == 'b_primary':
            return duplicate_match.contact_b_id, duplicate_match.contact_a_id
        else:
            # Default to A as primary
            return duplicate_match.contact_a_id, duplicate_match.contact_b_id
    
    async def _execute_merge(
        self,
        primary_contact: Contact,
        secondary_contact: Contact,
        conflicts: List[MergeConflict]
    ) -> MergeResult:
        """Execute the actual merge operation"""
        try:
            # Generate merged data
            merged_data = self._generate_merged_data(primary_contact, secondary_contact, conflicts)
            
            # Update primary contact with merged data
            for field_name, value in merged_data.items():
                if hasattr(primary_contact, field_name):
                    setattr(primary_contact, field_name, value)
            
            # Update timestamps
            primary_contact.updated_at = datetime.now(timezone.utc)
            
            # Merge interactions
            interactions_merged = self._merge_interactions(primary_contact.id, secondary_contact.id)
            
            # Merge interests
            interests_merged = self._merge_interests(primary_contact.id, secondary_contact.id)
            
            # Archive secondary contact instead of deleting
            secondary_contact.is_archived = True
            secondary_contact.updated_at = datetime.now(timezone.utc)
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Successfully merged contact {secondary_contact.id} into {primary_contact.id}")
            
            return MergeResult(
                success=True,
                merged_contact_id=str(primary_contact.id),
                removed_contact_id=str(secondary_contact.id),
                conflicts_resolved=conflicts,
                data_preserved=merged_data,
                interactions_merged=interactions_merged,
                interests_merged=interests_merged
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error executing merge: {e}")
            raise
    
    def _merge_interactions(self, primary_contact_id: str, secondary_contact_id: str) -> int:
        """Merge interactions from secondary to primary contact"""
        interactions = self.db.query(Interaction).filter(
            Interaction.contact_id == secondary_contact_id
        ).all()
        
        for interaction in interactions:
            interaction.contact_id = primary_contact_id
            interaction.updated_at = datetime.now(timezone.utc)
        
        return len(interactions)
    
    def _merge_interests(self, primary_contact_id: str, secondary_contact_id: str) -> int:
        """Merge interests from secondary to primary contact"""
        interests = self.db.query(Interest).filter(
            Interest.contact_id == secondary_contact_id
        ).all()
        
        merged_count = 0
        for interest in interests:
            # Check if primary contact already has this interest
            existing = self.db.query(Interest).filter(
                and_(
                    Interest.contact_id == primary_contact_id,
                    Interest.interest_category == interest.interest_category,
                    Interest.interest_topic == interest.interest_topic
                )
            ).first()
            
            if existing:
                # Merge confidence scores (take higher)
                if interest.confidence_score > existing.confidence_score:
                    existing.confidence_score = interest.confidence_score
                    existing.updated_at = datetime.now(timezone.utc)
                # Archive the duplicate interest
                interest.contact_id = None  # This will be cleaned up later
            else:
                # Move interest to primary contact
                interest.contact_id = primary_contact_id
                interest.updated_at = datetime.now(timezone.utc)
                merged_count += 1
        
        return merged_count 