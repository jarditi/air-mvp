"""
Unified Contact Management API Routes

This module provides comprehensive contact management endpoints that unify
all contact-related functionality across email, calendar, scoring, and deduplication.
"""

import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from pydantic import BaseModel, Field

from lib.database import get_db
from services.auth import get_current_user
from services.contact_scoring import ContactScoringService
from services.contact_relationship_integration import ContactRelationshipIntegrationService
from models.orm.user import User
from models.orm.contact import Contact
from models.orm.interaction import Interaction

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic Models

class ContactCreateRequest(BaseModel):
    """Request model for creating a new contact"""
    email: Optional[str] = Field(None, description="Contact email address")
    full_name: Optional[str] = Field(None, description="Full name")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    company: Optional[str] = Field(None, description="Company name")
    job_title: Optional[str] = Field(None, description="Job title")
    phone: Optional[str] = Field(None, description="Phone number")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    location: Optional[str] = Field(None, description="Location")
    bio: Optional[str] = Field(None, description="Biography")
    tags: Optional[List[str]] = Field(None, description="Contact tags")
    notes: Optional[str] = Field(None, description="Notes about the contact")
    contact_source: str = Field("manual", description="Source of the contact")


class ContactUpdateRequest(BaseModel):
    """Request model for updating a contact"""
    email: Optional[str] = None
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    is_archived: Optional[bool] = None


class ContactResponse(BaseModel):
    """Response model for contact data"""
    id: str
    email: Optional[str]
    full_name: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    company: Optional[str]
    job_title: Optional[str]
    phone: Optional[str]
    linkedin_url: Optional[str]
    location: Optional[str]
    bio: Optional[str]
    relationship_strength: Optional[float]
    last_interaction_at: Optional[str]
    interaction_frequency: Optional[str]
    contact_source: Optional[str]
    is_archived: bool
    tags: Optional[List[str]]
    notes: Optional[str]
    created_at: str
    updated_at: str


class ContactListResponse(BaseModel):
    """Response model for contact list"""
    contacts: List[ContactResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class ContactStatsResponse(BaseModel):
    """Response model for contact statistics"""
    total_contacts: int
    active_contacts: int
    archived_contacts: int
    by_source: Dict[str, int]
    by_tier: Dict[str, int]
    by_interaction_frequency: Dict[str, int]
    average_relationship_strength: float
    recent_interactions_30d: int
    last_updated: str


class BulkContactOperation(BaseModel):
    """Request model for bulk contact operations"""
    contact_ids: List[str] = Field(..., description="List of contact IDs")
    operation: str = Field(..., description="Operation type: archive, unarchive, delete, tag, untag")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Operation-specific parameters")


@router.get("/", response_model=ContactListResponse)
async def get_contacts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    search: Optional[str] = Query(None, description="Search query for name, email, or company"),
    tier: Optional[str] = Query(None, description="Filter by relationship tier"),
    source: Optional[str] = Query(None, description="Filter by contact source"),
    company: Optional[str] = Query(None, description="Filter by company"),
    interaction_frequency: Optional[str] = Query(None, description="Filter by interaction frequency"),
    is_archived: Optional[bool] = Query(False, description="Include archived contacts"),
    sort_by: str = Query("relationship_strength", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    min_relationship_strength: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum relationship strength"),
    max_days_since_interaction: Optional[int] = Query(None, ge=0, description="Maximum days since last interaction"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get contacts with advanced filtering, sorting, and pagination
    
    This endpoint provides a unified view of all contacts with comprehensive
    filtering options and relationship intelligence.
    """
    try:
        # Build base query
        query = db.query(Contact).filter(Contact.user_id == current_user.id)
        
        # Apply filters
        if not is_archived:
            query = query.filter(Contact.is_archived == False)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Contact.full_name.ilike(search_term),
                    Contact.email.ilike(search_term),
                    Contact.company.ilike(search_term),
                    Contact.first_name.ilike(search_term),
                    Contact.last_name.ilike(search_term)
                )
            )
        
        if source:
            query = query.filter(Contact.contact_source == source)
        
        if company:
            query = query.filter(Contact.company.ilike(f"%{company}%"))
        
        if interaction_frequency:
            query = query.filter(Contact.interaction_frequency == interaction_frequency)
        
        if min_relationship_strength is not None:
            query = query.filter(Contact.relationship_strength >= min_relationship_strength)
        
        if max_days_since_interaction is not None:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_days_since_interaction)
            query = query.filter(Contact.last_interaction_at >= cutoff_date)
        
        # Apply tier filter (requires relationship strength calculation)
        if tier:
            tier_thresholds = {
                "inner_circle": (0.8, 1.0),
                "strong_network": (0.6, 0.8),
                "active_network": (0.4, 0.6),
                "peripheral": (0.2, 0.4),
                "dormant": (0.0, 0.2)
            }
            if tier in tier_thresholds:
                min_score, max_score = tier_thresholds[tier]
                query = query.filter(
                    and_(
                        Contact.relationship_strength >= min_score,
                        Contact.relationship_strength < max_score if tier != "inner_circle" else Contact.relationship_strength <= max_score
                    )
                )
        
        # Apply sorting
        sort_field = getattr(Contact, sort_by, Contact.relationship_strength)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        contacts = query.offset(offset).limit(page_size).all()
        
        # Convert to response format
        contact_responses = []
        for contact in contacts:
            contact_responses.append(ContactResponse(
                id=str(contact.id),
                email=contact.email,
                full_name=contact.full_name,
                first_name=contact.first_name,
                last_name=contact.last_name,
                company=contact.company,
                job_title=contact.job_title,
                phone=contact.phone,
                linkedin_url=contact.linkedin_url,
                location=contact.location,
                bio=contact.bio,
                relationship_strength=float(contact.relationship_strength) if contact.relationship_strength else None,
                last_interaction_at=contact.last_interaction_at.isoformat() if contact.last_interaction_at else None,
                interaction_frequency=contact.interaction_frequency,
                contact_source=contact.contact_source,
                is_archived=contact.is_archived,
                tags=contact.tags,
                notes=contact.notes,
                created_at=contact.created_at.isoformat(),
                updated_at=contact.updated_at.isoformat()
            ))
        
        return ContactListResponse(
            contacts=contact_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=offset + page_size < total_count,
            has_previous=page > 1
        )
        
    except Exception as e:
        logger.error(f"Failed to get contacts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get contacts: {str(e)}")


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact_by_id(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific contact by ID with full details"""
    try:
        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        ).first()
        
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        return ContactResponse(
            id=str(contact.id),
            email=contact.email,
            full_name=contact.full_name,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company=contact.company,
            job_title=contact.job_title,
            phone=contact.phone,
            linkedin_url=contact.linkedin_url,
            location=contact.location,
            bio=contact.bio,
            relationship_strength=float(contact.relationship_strength) if contact.relationship_strength else None,
            last_interaction_at=contact.last_interaction_at.isoformat() if contact.last_interaction_at else None,
            interaction_frequency=contact.interaction_frequency,
            contact_source=contact.contact_source,
            is_archived=contact.is_archived,
            tags=contact.tags,
            notes=contact.notes,
            created_at=contact.created_at.isoformat(),
            updated_at=contact.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contact {contact_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get contact: {str(e)}")


@router.post("/", response_model=ContactResponse)
async def create_contact(
    request: ContactCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new contact manually"""
    try:
        # Check for duplicate email
        if request.email:
            existing = db.query(Contact).filter(
                Contact.email == request.email,
                Contact.user_id == current_user.id,
                Contact.is_archived == False
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Contact with email {request.email} already exists"
                )
        
        # Create new contact
        contact = Contact(
            user_id=current_user.id,
            email=request.email,
            full_name=request.full_name,
            first_name=request.first_name,
            last_name=request.last_name,
            company=request.company,
            job_title=request.job_title,
            phone=request.phone,
            linkedin_url=request.linkedin_url,
            location=request.location,
            bio=request.bio,
            contact_source=request.contact_source,
            tags=request.tags,
            notes=request.notes,
            relationship_strength=0.0,
            is_archived=False
        )
        
        db.add(contact)
        db.commit()
        db.refresh(contact)
        
        logger.info(f"Created new contact {contact.id} for user {current_user.id}")
        
        return ContactResponse(
            id=str(contact.id),
            email=contact.email,
            full_name=contact.full_name,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company=contact.company,
            job_title=contact.job_title,
            phone=contact.phone,
            linkedin_url=contact.linkedin_url,
            location=contact.location,
            bio=contact.bio,
            relationship_strength=float(contact.relationship_strength) if contact.relationship_strength else None,
            last_interaction_at=contact.last_interaction_at.isoformat() if contact.last_interaction_at else None,
            interaction_frequency=contact.interaction_frequency,
            contact_source=contact.contact_source,
            is_archived=contact.is_archived,
            tags=contact.tags,
            notes=contact.notes,
            created_at=contact.created_at.isoformat(),
            updated_at=contact.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create contact: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create contact: {str(e)}")


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    request: ContactUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing contact"""
    try:
        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        ).first()
        
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        # Check for email conflicts if email is being updated
        if request.email and request.email != contact.email:
            existing = db.query(Contact).filter(
                Contact.email == request.email,
                Contact.user_id == current_user.id,
                Contact.id != contact_id,
                Contact.is_archived == False
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Another contact with email {request.email} already exists"
                )
        
        # Update fields
        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(contact, field, value)
        
        db.commit()
        db.refresh(contact)
        
        logger.info(f"Updated contact {contact_id} for user {current_user.id}")
        
        return ContactResponse(
            id=str(contact.id),
            email=contact.email,
            full_name=contact.full_name,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company=contact.company,
            job_title=contact.job_title,
            phone=contact.phone,
            linkedin_url=contact.linkedin_url,
            location=contact.location,
            bio=contact.bio,
            relationship_strength=float(contact.relationship_strength) if contact.relationship_strength else None,
            last_interaction_at=contact.last_interaction_at.isoformat() if contact.last_interaction_at else None,
            interaction_frequency=contact.interaction_frequency,
            contact_source=contact.contact_source,
            is_archived=contact.is_archived,
            tags=contact.tags,
            notes=contact.notes,
            created_at=contact.created_at.isoformat(),
            updated_at=contact.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update contact {contact_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update contact: {str(e)}")


@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: str,
    permanent: bool = Query(False, description="Permanently delete instead of archiving"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete or archive a contact"""
    try:
        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        ).first()
        
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        if permanent:
            # Permanent deletion
            db.delete(contact)
            action = "deleted"
        else:
            # Soft delete (archive)
            contact.is_archived = True
            action = "archived"
        
        db.commit()
        
        logger.info(f"Contact {contact_id} {action} for user {current_user.id}")
        
        return {
            "success": True,
            "message": f"Contact {action} successfully",
            "contact_id": contact_id,
            "action": action
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete contact {contact_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete contact: {str(e)}")


@router.get("/search/advanced")
async def advanced_contact_search(
    q: str = Query(..., description="Search query"),
    fields: Optional[str] = Query("all", description="Fields to search: all, name, email, company, notes"),
    fuzzy: bool = Query(True, description="Enable fuzzy matching"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Advanced contact search with fuzzy matching and field-specific search"""
    try:
        query = db.query(Contact).filter(
            Contact.user_id == current_user.id,
            Contact.is_archived == False
        )
        
        search_term = f"%{q}%" if fuzzy else q
        
        if fields == "all":
            # Search across all text fields
            query = query.filter(
                or_(
                    Contact.full_name.ilike(search_term),
                    Contact.email.ilike(search_term),
                    Contact.company.ilike(search_term),
                    Contact.job_title.ilike(search_term),
                    Contact.notes.ilike(search_term),
                    Contact.first_name.ilike(search_term),
                    Contact.last_name.ilike(search_term)
                )
            )
        elif fields == "name":
            query = query.filter(
                or_(
                    Contact.full_name.ilike(search_term),
                    Contact.first_name.ilike(search_term),
                    Contact.last_name.ilike(search_term)
                )
            )
        elif fields == "email":
            query = query.filter(Contact.email.ilike(search_term))
        elif fields == "company":
            query = query.filter(Contact.company.ilike(search_term))
        elif fields == "notes":
            query = query.filter(Contact.notes.ilike(search_term))
        
        # Order by relationship strength
        contacts = query.order_by(desc(Contact.relationship_strength)).limit(limit).all()
        
        results = []
        for contact in contacts:
            results.append({
                "id": str(contact.id),
                "full_name": contact.full_name,
                "email": contact.email,
                "company": contact.company,
                "job_title": contact.job_title,
                "relationship_strength": float(contact.relationship_strength) if contact.relationship_strength else 0.0,
                "last_interaction_at": contact.last_interaction_at.isoformat() if contact.last_interaction_at else None,
                "contact_source": contact.contact_source
            })
        
        return {
            "success": True,
            "query": q,
            "fields_searched": fields,
            "fuzzy_matching": fuzzy,
            "results_count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to search contacts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search contacts: {str(e)}")


@router.get("/stats", response_model=ContactStatsResponse)
async def get_contact_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive contact statistics"""
    try:
        # Get all contacts
        all_contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()
        active_contacts = [c for c in all_contacts if not c.is_archived]
        archived_contacts = [c for c in all_contacts if c.is_archived]
        
        # Source distribution
        source_counts = {}
        for contact in active_contacts:
            source = contact.contact_source or "unknown"
            source_counts[source] = source_counts.get(source, 0) + 1
        
        # Tier distribution
        tier_counts = {
            "inner_circle": 0,
            "strong_network": 0,
            "active_network": 0,
            "peripheral": 0,
            "dormant": 0
        }
        
        # Interaction frequency distribution
        frequency_counts = {
            "daily": 0,
            "weekly": 0,
            "monthly": 0,
            "quarterly": 0,
            "rarely": 0
        }
        
        # Calculate averages and distributions
        total_strength = 0.0
        strength_count = 0
        recent_interactions = 0
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        
        for contact in active_contacts:
            # Tier classification
            strength = float(contact.relationship_strength) if contact.relationship_strength else 0.0
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
            
            # Average strength
            if contact.relationship_strength:
                total_strength += strength
                strength_count += 1
            
            # Interaction frequency
            freq = contact.interaction_frequency or "rarely"
            if freq in frequency_counts:
                frequency_counts[freq] += 1
            
            # Recent interactions
            if contact.last_interaction_at and contact.last_interaction_at > cutoff_date:
                recent_interactions += 1
        
        avg_strength = total_strength / strength_count if strength_count > 0 else 0.0
        
        return ContactStatsResponse(
            total_contacts=len(all_contacts),
            active_contacts=len(active_contacts),
            archived_contacts=len(archived_contacts),
            by_source=source_counts,
            by_tier=tier_counts,
            by_interaction_frequency=frequency_counts,
            average_relationship_strength=round(avg_strength, 3),
            recent_interactions_30d=recent_interactions,
            last_updated=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to get contact stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get contact statistics: {str(e)}")


@router.post("/bulk-operations")
async def bulk_contact_operations(
    request: BulkContactOperation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Perform bulk operations on multiple contacts"""
    try:
        # Get contacts
        contacts = db.query(Contact).filter(
            Contact.id.in_(request.contact_ids),
            Contact.user_id == current_user.id
        ).all()
        
        if len(contacts) != len(request.contact_ids):
            raise HTTPException(
                status_code=400,
                detail="Some contact IDs were not found or don't belong to the user"
            )
        
        updated_count = 0
        
        if request.operation == "archive":
            for contact in contacts:
                contact.is_archived = True
                updated_count += 1
        
        elif request.operation == "unarchive":
            for contact in contacts:
                contact.is_archived = False
                updated_count += 1
        
        elif request.operation == "delete":
            for contact in contacts:
                db.delete(contact)
                updated_count += 1
        
        elif request.operation == "tag":
            tag = request.parameters.get("tag") if request.parameters else None
            if not tag:
                raise HTTPException(status_code=400, detail="Tag parameter required for tag operation")
            
            for contact in contacts:
                if not contact.tags:
                    contact.tags = []
                if tag not in contact.tags:
                    contact.tags.append(tag)
                updated_count += 1
        
        elif request.operation == "untag":
            tag = request.parameters.get("tag") if request.parameters else None
            if not tag:
                raise HTTPException(status_code=400, detail="Tag parameter required for untag operation")
            
            for contact in contacts:
                if contact.tags and tag in contact.tags:
                    contact.tags.remove(tag)
                    updated_count += 1
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {request.operation}")
        
        db.commit()
        
        logger.info(f"Bulk operation {request.operation} completed on {updated_count} contacts for user {current_user.id}")
        
        return {
            "success": True,
            "operation": request.operation,
            "contacts_processed": len(request.contact_ids),
            "contacts_updated": updated_count,
            "message": f"Bulk {request.operation} operation completed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to perform bulk operation: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to perform bulk operation: {str(e)}")


@router.post("/export")
async def export_contacts(
    format: str = Query("json", description="Export format: json or csv"),
    include_archived: bool = Query(False, description="Include archived contacts"),
    tier_filter: Optional[str] = Query(None, description="Filter by relationship tier"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export contacts in JSON or CSV format"""
    try:
        # Build query
        query = db.query(Contact).filter(Contact.user_id == current_user.id)
        
        if not include_archived:
            query = query.filter(Contact.is_archived == False)
        
        if tier_filter:
            tier_thresholds = {
                "inner_circle": (0.8, 1.0),
                "strong_network": (0.6, 0.8),
                "active_network": (0.4, 0.6),
                "peripheral": (0.2, 0.4),
                "dormant": (0.0, 0.2)
            }
            if tier_filter in tier_thresholds:
                min_score, max_score = tier_thresholds[tier_filter]
                query = query.filter(
                    and_(
                        Contact.relationship_strength >= min_score,
                        Contact.relationship_strength < max_score if tier_filter != "inner_circle" else Contact.relationship_strength <= max_score
                    )
                )
        
        contacts = query.all()
        
        # Prepare export data
        export_data = []
        for contact in contacts:
            export_data.append({
                "id": str(contact.id),
                "email": contact.email,
                "full_name": contact.full_name,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "company": contact.company,
                "job_title": contact.job_title,
                "phone": contact.phone,
                "linkedin_url": contact.linkedin_url,
                "location": contact.location,
                "bio": contact.bio,
                "relationship_strength": float(contact.relationship_strength) if contact.relationship_strength else None,
                "last_interaction_at": contact.last_interaction_at.isoformat() if contact.last_interaction_at else None,
                "interaction_frequency": contact.interaction_frequency,
                "contact_source": contact.contact_source,
                "is_archived": contact.is_archived,
                "tags": contact.tags,
                "notes": contact.notes,
                "created_at": contact.created_at.isoformat(),
                "updated_at": contact.updated_at.isoformat()
            })
        
        if format.lower() == "csv":
            # Convert to CSV format
            import csv
            import io
            
            output = io.StringIO()
            if export_data:
                writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
                writer.writeheader()
                writer.writerows(export_data)
            
            csv_content = output.getvalue()
            output.close()
            
            return {
                "success": True,
                "format": "csv",
                "contacts_count": len(export_data),
                "data": csv_content,
                "filename": f"contacts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        
        else:
            # JSON format
            return {
                "success": True,
                "format": "json",
                "contacts_count": len(export_data),
                "data": export_data,
                "filename": f"contacts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            }
        
    except Exception as e:
        logger.error(f"Failed to export contacts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export contacts: {str(e)}")


@router.post("/refresh-scores")
async def refresh_relationship_scores(
    background_tasks: BackgroundTasks,
    contact_ids: Optional[List[str]] = Query(None, description="Specific contact IDs to refresh"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Refresh relationship strength scores for contacts"""
    try:
        integration_service = ContactRelationshipIntegrationService()
        
        if contact_ids:
            # Refresh specific contacts
            results = []
            for contact_id in contact_ids:
                try:
                    result = await integration_service.update_contact_relationship_strength(
                        db=db,
                        user_id=str(current_user.id),
                        contact_id=contact_id
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to refresh score for contact {contact_id}: {e}")
                    results.append({"contact_id": contact_id, "error": str(e)})
            
            return {
                "success": True,
                "message": "Relationship scores refreshed for specified contacts",
                "contacts_processed": len(contact_ids),
                "results": results
            }
        
        else:
            # Refresh all contacts in background
            background_tasks.add_task(
                _background_refresh_all_scores,
                db=db,
                user_id=str(current_user.id)
            )
            
            return {
                "success": True,
                "message": "Relationship score refresh queued for all contacts",
                "user_id": str(current_user.id),
                "estimated_completion": "5-15 minutes depending on contact count"
            }
        
    except Exception as e:
        logger.error(f"Failed to refresh relationship scores: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh scores: {str(e)}")


# Background task functions

async def _background_refresh_all_scores(db: Session, user_id: str):
    """Background task to refresh all contact relationship scores"""
    try:
        integration_service = ContactRelationshipIntegrationService()
        result = await integration_service.update_all_contacts_relationship_strength(db, user_id)
        logger.info(f"Background score refresh completed for user {user_id}: {result}")
    except Exception as e:
        logger.error(f"Background score refresh failed for user {user_id}: {e}")


# Import missing dependencies
from datetime import timedelta 