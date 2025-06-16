"""
Contact Deduplication API Routes (Task 2.5.5)

REST API endpoints for contact deduplication, merging, and duplicate management.
Provides both automated and manual workflows for handling duplicate contacts.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from lib.database import get_db
from services.auth import get_current_user
from models.orm.user import User
from services.contact_deduplication import ContactDeduplicationService, DuplicateMatch
from services.contact_merging import ContactMergingService, MergeResult, MergePreview, MergeConflict

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Contact Deduplication"])


# Request/Response Models

class DuplicateScanRequest(BaseModel):
    """Request model for duplicate scanning"""
    include_low_confidence: bool = Field(False, description="Include low confidence matches")
    batch_size: int = Field(100, description="Batch size for processing", ge=10, le=1000)


class ContactDuplicateResponse(BaseModel):
    """Response model for duplicate contact information"""
    contact_a_id: str
    contact_b_id: str
    confidence_score: float
    matching_strategy: str
    matching_fields: List[str]
    conflicting_fields: List[str]
    recommended_action: str
    merge_priority: str
    evidence: Dict[str, Any]


class DuplicateScanResponse(BaseModel):
    """Response model for duplicate scan results"""
    total_contacts_scanned: int
    duplicates_found: int
    auto_merge_candidates: int
    manual_review_candidates: int
    low_confidence_matches: int
    duplicates: List[ContactDuplicateResponse]
    scan_duration_seconds: float


class MergePreviewRequest(BaseModel):
    """Request model for merge preview"""
    primary_contact_id: str = Field(..., description="Contact ID to keep")
    secondary_contact_id: str = Field(..., description="Contact ID to merge and remove")


class MergeConflictResponse(BaseModel):
    """Response model for merge conflicts"""
    field_name: str
    primary_value: Any
    secondary_value: Any
    recommended_strategy: str
    confidence: float
    reason: str


class MergePreviewResponse(BaseModel):
    """Response model for merge preview"""
    primary_contact_id: str
    secondary_contact_id: str
    merged_data: Dict[str, Any]
    conflicts: List[MergeConflictResponse]
    interactions_to_merge: int
    interests_to_merge: int
    estimated_data_loss: List[str]


class MergeContactsRequest(BaseModel):
    """Request model for contact merging"""
    primary_contact_id: str = Field(..., description="Contact ID to keep")
    secondary_contact_id: str = Field(..., description="Contact ID to merge and remove")
    conflict_resolutions: Optional[Dict[str, str]] = Field(None, description="Manual conflict resolutions")
    dry_run: bool = Field(False, description="Preview merge without executing")


class MergeContactsResponse(BaseModel):
    """Response model for contact merge results"""
    success: bool
    merged_contact_id: str
    removed_contact_id: str
    conflicts_resolved: int
    data_preserved: Dict[str, Any]
    interactions_merged: int
    interests_merged: int
    error_message: Optional[str] = None


class AutoMergeRequest(BaseModel):
    """Request model for auto-merge operation"""
    max_merges: int = Field(50, description="Maximum number of merges to perform", ge=1, le=100)
    confidence_threshold: float = Field(0.90, description="Minimum confidence for auto-merge", ge=0.8, le=1.0)


class AutoMergeResponse(BaseModel):
    """Response model for auto-merge results"""
    merges_attempted: int
    merges_successful: int
    merges_failed: int
    total_contacts_merged: int
    results: List[MergeContactsResponse]


class DeduplicationStatsResponse(BaseModel):
    """Response model for deduplication statistics"""
    total_contacts: int
    potential_duplicates: int
    auto_merge_candidates: int
    manual_review_candidates: int
    last_scan_date: Optional[str]
    duplicate_rate: float
    data_quality_score: float


# API Endpoints

@router.post("/scan", response_model=DuplicateScanResponse)
async def scan_for_duplicates(
    request: DuplicateScanRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Scan all contacts for potential duplicates
    
    This endpoint analyzes all contacts for a user to identify potential duplicates
    using advanced fuzzy matching algorithms and confidence scoring.
    
    Args:
        request: Duplicate scan parameters
        background_tasks: Background task manager
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Comprehensive duplicate scan results
    """
    try:
        start_time = datetime.now()
        
        service = ContactDeduplicationService(db)
        
        # Perform duplicate scan
        duplicates = await service.scan_all_duplicates(
            user_id=str(current_user.id),
            batch_size=request.batch_size,
            include_low_confidence=request.include_low_confidence
        )
        
        # Categorize duplicates by confidence
        auto_merge_candidates = [d for d in duplicates if d.confidence_score >= 0.90]
        manual_review_candidates = [d for d in duplicates if 0.30 <= d.confidence_score < 0.90]
        low_confidence_matches = [d for d in duplicates if d.confidence_score < 0.30]
        
        # Convert to response format
        duplicate_responses = []
        for duplicate in duplicates:
            duplicate_responses.append(ContactDuplicateResponse(
                contact_a_id=duplicate.contact_a_id,
                contact_b_id=duplicate.contact_b_id,
                confidence_score=duplicate.confidence_score,
                matching_strategy=duplicate.matching_strategy.strategy_name,
                matching_fields=duplicate.matching_fields,
                conflicting_fields=duplicate.conflicting_fields,
                recommended_action=duplicate.recommended_action,
                merge_priority=duplicate.merge_priority,
                evidence=duplicate.evidence
            ))
        
        # Calculate scan duration
        scan_duration = (datetime.now() - start_time).total_seconds()
        
        # Get total contacts count for context
        from models.orm.contact import Contact
        total_contacts = db.query(Contact).filter(
            Contact.user_id == current_user.id,
            Contact.is_archived == False
        ).count()
        
        logger.info(f"Duplicate scan completed for user {current_user.id}: "
                   f"{len(duplicates)} duplicates found in {scan_duration:.2f}s")
        
        return {
            "total_contacts_scanned": total_contacts,
            "duplicates_found": len(duplicates),
            "auto_merge_candidates": len(auto_merge_candidates),
            "manual_review_candidates": len(manual_review_candidates),
            "low_confidence_matches": len(low_confidence_matches),
            "duplicates": duplicate_responses,
            "scan_duration_seconds": scan_duration
        }
        
    except Exception as e:
        logger.error(f"Error scanning for duplicates: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to scan for duplicates: {str(e)}"
        )


@router.get("/contact/{contact_id}/duplicates")
async def find_duplicates_for_contact(
    contact_id: str,
    include_low_confidence: bool = Query(False, description="Include low confidence matches"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[ContactDuplicateResponse]:
    """
    Find potential duplicates for a specific contact
    
    Args:
        contact_id: Contact ID to find duplicates for
        include_low_confidence: Include matches below manual review threshold
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of potential duplicate matches
    """
    try:
        service = ContactDeduplicationService(db)
        
        duplicates = await service.find_duplicates_for_contact(
            user_id=str(current_user.id),
            contact_id=contact_id,
            include_low_confidence=include_low_confidence
        )
        
        # Convert to response format
        duplicate_responses = []
        for duplicate in duplicates:
            duplicate_responses.append(ContactDuplicateResponse(
                contact_a_id=duplicate.contact_a_id,
                contact_b_id=duplicate.contact_b_id,
                confidence_score=duplicate.confidence_score,
                matching_strategy=duplicate.matching_strategy.strategy_name,
                matching_fields=duplicate.matching_fields,
                conflicting_fields=duplicate.conflicting_fields,
                recommended_action=duplicate.recommended_action,
                merge_priority=duplicate.merge_priority,
                evidence=duplicate.evidence
            ))
        
        logger.info(f"Found {len(duplicates)} potential duplicates for contact {contact_id}")
        return duplicate_responses
        
    except Exception as e:
        logger.error(f"Error finding duplicates for contact {contact_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to find duplicates: {str(e)}"
        )


@router.post("/merge/preview", response_model=MergePreviewResponse)
async def preview_contact_merge(
    request: MergePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Preview what would happen in a contact merge operation
    
    Args:
        request: Merge preview parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Preview of merge operation including conflicts and data changes
    """
    try:
        service = ContactMergingService(db)
        
        preview = await service.preview_merge(
            user_id=str(current_user.id),
            primary_contact_id=request.primary_contact_id,
            secondary_contact_id=request.secondary_contact_id
        )
        
        # Convert conflicts to response format
        conflict_responses = []
        for conflict in preview.conflicts:
            conflict_responses.append(MergeConflictResponse(
                field_name=conflict.field_name,
                primary_value=conflict.primary_value,
                secondary_value=conflict.secondary_value,
                recommended_strategy=conflict.recommended_strategy.value,
                confidence=conflict.confidence,
                reason=conflict.reason
            ))
        
        return {
            "primary_contact_id": preview.primary_contact_id,
            "secondary_contact_id": preview.secondary_contact_id,
            "merged_data": preview.merged_data,
            "conflicts": conflict_responses,
            "interactions_to_merge": preview.interactions_to_merge,
            "interests_to_merge": preview.interests_to_merge,
            "estimated_data_loss": preview.estimated_data_loss
        }
        
    except Exception as e:
        logger.error(f"Error previewing merge: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to preview merge: {str(e)}"
        )


@router.post("/merge", response_model=MergeContactsResponse)
async def merge_contacts(
    request: MergeContactsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Merge two contacts with optional conflict resolution
    
    Args:
        request: Merge request parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Result of merge operation
    """
    try:
        service = ContactMergingService(db)
        
        result = await service.merge_contacts(
            user_id=str(current_user.id),
            primary_contact_id=request.primary_contact_id,
            secondary_contact_id=request.secondary_contact_id,
            conflict_resolutions=request.conflict_resolutions,
            dry_run=request.dry_run
        )
        
        return {
            "success": result.success,
            "merged_contact_id": result.merged_contact_id,
            "removed_contact_id": result.removed_contact_id,
            "conflicts_resolved": len(result.conflicts_resolved),
            "data_preserved": result.data_preserved,
            "interactions_merged": result.interactions_merged,
            "interests_merged": result.interests_merged,
            "error_message": result.error_message
        }
        
    except Exception as e:
        logger.error(f"Error merging contacts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to merge contacts: {str(e)}"
        )


@router.post("/auto-merge", response_model=AutoMergeResponse)
async def auto_merge_duplicates(
    request: AutoMergeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Automatically merge high-confidence duplicate contacts
    
    Args:
        request: Auto-merge parameters
        background_tasks: Background task manager
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Results of auto-merge operation
    """
    try:
        service = ContactMergingService(db)
        
        # Perform auto-merge
        results = await service.auto_merge_high_confidence(
            user_id=str(current_user.id),
            max_merges=request.max_merges
        )
        
        # Convert results to response format
        merge_responses = []
        successful_merges = 0
        failed_merges = 0
        
        for result in results:
            merge_responses.append(MergeContactsResponse(
                success=result.success,
                merged_contact_id=result.merged_contact_id,
                removed_contact_id=result.removed_contact_id,
                conflicts_resolved=len(result.conflicts_resolved),
                data_preserved=result.data_preserved,
                interactions_merged=result.interactions_merged,
                interests_merged=result.interests_merged,
                error_message=result.error_message
            ))
            
            if result.success:
                successful_merges += 1
            else:
                failed_merges += 1
        
        logger.info(f"Auto-merge completed: {successful_merges} successful, {failed_merges} failed")
        
        return {
            "merges_attempted": len(results),
            "merges_successful": successful_merges,
            "merges_failed": failed_merges,
            "total_contacts_merged": successful_merges * 2,  # Each merge combines 2 contacts
            "results": merge_responses
        }
        
    except Exception as e:
        logger.error(f"Error in auto-merge: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to auto-merge contacts: {str(e)}"
        )


@router.get("/suggestions/auto-merge")
async def get_auto_merge_suggestions(
    limit: int = Query(20, description="Maximum suggestions to return", ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[ContactDuplicateResponse]:
    """
    Get high-confidence duplicate contacts suitable for auto-merge
    
    Args:
        limit: Maximum number of suggestions to return
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of auto-merge candidate duplicates
    """
    try:
        service = ContactDeduplicationService(db)
        
        candidates = await service.get_auto_merge_candidates(str(current_user.id))
        
        # Limit results
        candidates = candidates[:limit]
        
        # Convert to response format
        suggestions = []
        for candidate in candidates:
            suggestions.append(ContactDuplicateResponse(
                contact_a_id=candidate.contact_a_id,
                contact_b_id=candidate.contact_b_id,
                confidence_score=candidate.confidence_score,
                matching_strategy=candidate.matching_strategy.strategy_name,
                matching_fields=candidate.matching_fields,
                conflicting_fields=candidate.conflicting_fields,
                recommended_action=candidate.recommended_action,
                merge_priority=candidate.merge_priority,
                evidence=candidate.evidence
            ))
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Error getting auto-merge suggestions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get auto-merge suggestions: {str(e)}"
        )


@router.get("/suggestions/manual-review")
async def get_manual_review_suggestions(
    limit: int = Query(20, description="Maximum suggestions to return", ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[ContactDuplicateResponse]:
    """
    Get medium-confidence duplicate contacts requiring manual review
    
    Args:
        limit: Maximum number of suggestions to return
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of manual review candidate duplicates
    """
    try:
        service = ContactDeduplicationService(db)
        
        candidates = await service.get_manual_review_candidates(str(current_user.id))
        
        # Limit results
        candidates = candidates[:limit]
        
        # Convert to response format
        suggestions = []
        for candidate in candidates:
            suggestions.append(ContactDuplicateResponse(
                contact_a_id=candidate.contact_a_id,
                contact_b_id=candidate.contact_b_id,
                confidence_score=candidate.confidence_score,
                matching_strategy=candidate.matching_strategy.strategy_name,
                matching_fields=candidate.matching_fields,
                conflicting_fields=candidate.conflicting_fields,
                recommended_action=candidate.recommended_action,
                merge_priority=candidate.merge_priority,
                evidence=candidate.evidence
            ))
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Error getting manual review suggestions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get manual review suggestions: {str(e)}"
        )


@router.get("/stats", response_model=DeduplicationStatsResponse)
async def get_deduplication_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get deduplication statistics for the user's contacts
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Comprehensive deduplication statistics
    """
    try:
        from models.orm.contact import Contact
        
        # Get total contacts
        total_contacts = db.query(Contact).filter(
            Contact.user_id == current_user.id,
            Contact.is_archived == False
        ).count()
        
        if total_contacts == 0:
            return {
                "total_contacts": 0,
                "potential_duplicates": 0,
                "auto_merge_candidates": 0,
                "manual_review_candidates": 0,
                "last_scan_date": None,
                "duplicate_rate": 0.0,
                "data_quality_score": 1.0
            }
        
        # Get duplicate counts
        service = ContactDeduplicationService(db)
        all_duplicates = await service.scan_all_duplicates(str(current_user.id))
        
        auto_merge_candidates = len([d for d in all_duplicates if d.confidence_score >= 0.90])
        manual_review_candidates = len([d for d in all_duplicates if 0.30 <= d.confidence_score < 0.90])
        
        # Calculate duplicate rate
        duplicate_rate = len(all_duplicates) / total_contacts if total_contacts > 0 else 0.0
        
        # Calculate data quality score (inverse of duplicate rate)
        data_quality_score = max(0.0, 1.0 - duplicate_rate)
        
        return {
            "total_contacts": total_contacts,
            "potential_duplicates": len(all_duplicates),
            "auto_merge_candidates": auto_merge_candidates,
            "manual_review_candidates": manual_review_candidates,
            "last_scan_date": datetime.now().isoformat(),
            "duplicate_rate": duplicate_rate,
            "data_quality_score": data_quality_score
        }
        
    except Exception as e:
        logger.error(f"Error getting deduplication statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get deduplication statistics: {str(e)}"
        ) 