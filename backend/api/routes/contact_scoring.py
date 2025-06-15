"""
Contact Scoring API Routes

This module provides REST API endpoints for contact quality scoring functionality.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging

from lib.database import get_db
from models.orm.contact import Contact
from models.orm.interaction import Interaction
from models.orm.user import User
from services.contact_scoring import ContactScoringService, ScoringWeights
from services.auth import get_current_user
from services.contact_relationship_integration import ContactRelationshipIntegrationService

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/contact-scoring", tags=["contact-scoring"])

# Initialize scoring service
scoring_service = ContactScoringService()


@router.get("/health")
async def health_check():
    """Health check endpoint for contact scoring service"""
    return {
        "status": "healthy",
        "service": "contact-scoring",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/tiers")
async def get_contact_tiers():
    """Get available contact tiers and their descriptions"""
    return scoring_service.get_contact_tiers()


@router.get("/scoring-weights")
async def get_default_scoring_weights():
    """Get default scoring weights"""
    return scoring_service.get_default_weights()


@router.post("/score-contact/{contact_id}")
async def score_individual_contact(
    contact_id: str,
    custom_weights: Optional[ScoringWeights] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Score an individual contact
    
    Args:
        contact_id: UUID of the contact to score
        custom_weights: Optional custom scoring weights
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Comprehensive scoring result for the contact
    """
    
    try:
        # Get contact
        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        ).first()
        
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        # Get interactions for this contact
        interactions = db.query(Interaction).filter(
            Interaction.contact_id == contact_id,
            Interaction.user_id == current_user.id
        ).all()
        
        # Convert to dict format for scoring service
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
        
        # Score the contact
        result = await scoring_service.score_contact(
            contact_data=contact_data,
            interactions=interactions_data,
            custom_weights=custom_weights
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scoring contact {contact_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/score-contacts-batch")
async def score_contacts_batch(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Score multiple contacts in batch
    
    Args:
        request: Request containing contact_ids and optional custom_weights
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of scoring results
    """
    
    try:
        contact_ids = request.get("contact_ids", [])
        custom_weights_data = request.get("custom_weights")
        
        if not contact_ids:
            raise HTTPException(status_code=400, detail="contact_ids is required")
        
        if len(contact_ids) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 contacts per batch")
        
        # Parse custom weights if provided
        custom_weights = None
        if custom_weights_data:
            try:
                custom_weights = ScoringWeights(**custom_weights_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid custom weights: {e}")
        
        # Get contacts
        contacts = db.query(Contact).filter(
            Contact.id.in_(contact_ids),
            Contact.user_id == current_user.id
        ).all()
        
        # Prepare batch data
        batch_data = []
        for contact in contacts:
            # Get interactions for this contact
            interactions = db.query(Interaction).filter(
                Interaction.contact_id == contact.id,
                Interaction.user_id == current_user.id
            ).all()
            
            # Convert to dict format
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
            
            batch_data.append({
                "contact_data": contact_data,
                "interactions": interactions_data
            })
        
        # Score contacts in batch
        results = await scoring_service.score_contacts_batch(
            contacts_data=batch_data,
            custom_weights=custom_weights
        )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch scoring: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/score-all-contacts")
async def score_all_contacts(
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Maximum number of contacts to return"),
    offset: Optional[int] = Query(0, ge=0, description="Number of contacts to skip"),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum score threshold"),
    max_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Maximum score threshold"),
    tier_filter: Optional[str] = Query(None, description="Filter by contact tier"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Score all contacts for the current user with optional filtering
    
    Args:
        limit: Maximum number of contacts to return
        offset: Number of contacts to skip
        min_score: Minimum score threshold
        max_score: Maximum score threshold
        tier_filter: Filter by contact tier
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of scored contacts, sorted by score (highest first)
    """
    
    try:
        # Validate tier filter
        valid_tiers = ["inner_circle", "strong_network", "active_network", "peripheral", "dormant"]
        if tier_filter and tier_filter not in valid_tiers:
            raise HTTPException(status_code=400, detail=f"Invalid tier filter. Must be one of: {valid_tiers}")
        
        # Get all contacts for user
        contacts_query = db.query(Contact).filter(Contact.user_id == current_user.id)
        
        if limit:
            contacts_query = contacts_query.limit(limit + offset)  # Get extra for offset
        
        contacts = contacts_query.all()
        
        if offset:
            contacts = contacts[offset:]
        
        # Prepare batch data
        batch_data = []
        for contact in contacts:
            # Get interactions for this contact
            interactions = db.query(Interaction).filter(
                Interaction.contact_id == contact.id,
                Interaction.user_id == current_user.id
            ).all()
            
            # Convert to dict format
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
            
            batch_data.append({
                "contact_data": contact_data,
                "interactions": interactions_data
            })
        
        # Score all contacts
        results = await scoring_service.score_contacts_batch(batch_data)
        
        # Apply filters
        filtered_results = []
        for result in results:
            # Score filters
            if min_score is not None and result["overall_score"] < min_score:
                continue
            if max_score is not None and result["overall_score"] > max_score:
                continue
            
            # Tier filter
            if tier_filter and result["tier"] != tier_filter:
                continue
            
            filtered_results.append(result)
        
        # Sort by score (highest first)
        filtered_results.sort(key=lambda x: x["overall_score"], reverse=True)
        
        # Apply limit after filtering and sorting
        if limit:
            filtered_results = filtered_results[:limit]
        
        return filtered_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scoring all contacts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scoring-stats")
async def get_scoring_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive scoring statistics for the user's contacts
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Statistics about contact scores and tiers
    """
    
    try:
        # Get all contacts for user
        contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()
        
        if not contacts:
            return {
                "total_contacts": 0,
                "average_score": 0.0,
                "tier_distribution": {tier: 0 for tier in ["inner_circle", "strong_network", "active_network", "peripheral", "dormant"]},
                "score_distribution": {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0},
                "top_contacts": []
            }
        
        # Prepare batch data for scoring
        batch_data = []
        for contact in contacts:
            # Get interactions for this contact
            interactions = db.query(Interaction).filter(
                Interaction.contact_id == contact.id,
                Interaction.user_id == current_user.id
            ).all()
            
            # Convert to dict format
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
            
            batch_data.append({
                "contact_data": contact_data,
                "interactions": interactions_data
            })
        
        # Score all contacts
        results = await scoring_service.score_contacts_batch(batch_data)
        
        # Calculate statistics
        total_contacts = len(results)
        scores = [result["overall_score"] for result in results]
        average_score = sum(scores) / len(scores) if scores else 0.0
        
        # Tier distribution
        tier_distribution = {
            "inner_circle": 0,
            "strong_network": 0,
            "active_network": 0,
            "peripheral": 0,
            "dormant": 0
        }
        
        for result in results:
            tier = result["tier"]
            if tier in tier_distribution:
                tier_distribution[tier] += 1
        
        # Score distribution
        score_distribution = {
            "0.0-0.2": 0,
            "0.2-0.4": 0,
            "0.4-0.6": 0,
            "0.6-0.8": 0,
            "0.8-1.0": 0
        }
        
        for score in scores:
            if score < 0.2:
                score_distribution["0.0-0.2"] += 1
            elif score < 0.4:
                score_distribution["0.2-0.4"] += 1
            elif score < 0.6:
                score_distribution["0.4-0.6"] += 1
            elif score < 0.8:
                score_distribution["0.6-0.8"] += 1
            else:
                score_distribution["0.8-1.0"] += 1
        
        # Top contacts (top 5 by score)
        top_contacts = sorted(results, key=lambda x: x["overall_score"], reverse=True)[:5]
        top_contacts_summary = []
        for contact in top_contacts:
            top_contacts_summary.append({
                "contact_id": contact["contact_id"],
                "name": next((c.full_name for c in contacts if str(c.id) == contact["contact_id"]), "Unknown"),
                "score": contact["overall_score"],
                "tier": contact["tier"]
            })
        
        return {
            "total_contacts": total_contacts,
            "average_score": round(average_score, 3),
            "tier_distribution": tier_distribution,
            "score_distribution": score_distribution,
            "top_contacts": top_contacts_summary,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting scoring statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/update-relationship-strength/{contact_id}")
async def update_contact_relationship_strength(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update relationship strength for a specific contact using contact scoring
    """
    try:
        integration_service = ContactRelationshipIntegrationService()
        
        result = await integration_service.update_contact_relationship_strength(
            db=db,
            user_id=str(current_user.id),
            contact_id=contact_id
        )
        
        return {
            "success": True,
            "message": "Relationship strength updated successfully",
            "data": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update relationship strength: {e}")
        raise HTTPException(status_code=500, detail="Failed to update relationship strength")


@router.post("/update-all-relationship-strengths")
async def update_all_relationship_strengths(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update relationship strength for all contacts using contact scoring
    """
    try:
        integration_service = ContactRelationshipIntegrationService()
        
        result = await integration_service.update_all_contacts_relationship_strength(
            db=db,
            user_id=str(current_user.id)
        )
        
        return {
            "success": True,
            "message": "All relationship strengths updated successfully",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Failed to update all relationship strengths: {e}")
        raise HTTPException(status_code=500, detail="Failed to update relationship strengths") 