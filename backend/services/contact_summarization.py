"""
Contact Summarization Service

This service provides AI-powered contact summarization capabilities,
leveraging existing infrastructure from conversation threading, AI assistant,
and contact management systems.
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from lib.llm_client import get_openai_client, OpenAIModel
from lib.logger import logger
from models.orm.contact import Contact
from models.orm.interaction import Interaction
from services.conversation_threading_service import ConversationThread
from services.ai_assistant import AIAssistantService
from services.conversation_threading_service import ConversationThreadingService

# logger already imported from lib.logger


class ContactSummarizationError(Exception):
    """Exception raised for contact summarization errors."""
    pass


class SummaryType:
    """Summary type constants."""
    COMPREHENSIVE = "comprehensive"
    BRIEF = "brief"
    PRE_MEETING = "pre_meeting"
    RELATIONSHIP_STATUS = "relationship_status"
    UPDATES = "updates"


class ContactSummarizationService:
    """Service for generating AI-powered contact summaries."""
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIAssistantService(db)
        self.threading_service = ConversationThreadingService(db)
        self.openai_client = get_openai_client()
        
        # Cache settings
        self.cache_duration_hours = {
            SummaryType.COMPREHENSIVE: 24,
            SummaryType.BRIEF: 12,
            SummaryType.PRE_MEETING: 1,  # Very short cache for meetings
            SummaryType.RELATIONSHIP_STATUS: 168,  # 1 week
            SummaryType.UPDATES: 6
        }
    
    async def generate_contact_summary(
        self,
        contact_id: UUID,
        user_id: UUID,
        summary_type: str = SummaryType.COMPREHENSIVE,
        meeting_context: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Generate an AI-powered summary for a contact.
        
        Args:
            contact_id: ID of the contact to summarize
            user_id: ID of the requesting user
            summary_type: Type of summary to generate
            meeting_context: Optional context for pre-meeting summaries
            force_refresh: Skip cache and generate fresh summary
            
        Returns:
            Dictionary containing the generated summary and metadata
        """
        try:
            # Get contact with validation
            contact = self._get_contact_with_validation(contact_id, user_id)
            
            # Check cache first (unless force refresh)
            if not force_refresh:
                cached_summary = await self._get_cached_summary(
                    contact_id, user_id, summary_type
                )
                if cached_summary:
                    return cached_summary
            
            # Gather contact data
            contact_data = await self._gather_contact_data(contact_id, user_id)
            
            # Generate summary based on type
            summary_content = await self._generate_summary_content(
                contact_data, summary_type, meeting_context
            )
            
            # Create summary response
            summary = {
                "contact_id": str(contact_id),
                "contact_name": contact.full_name,
                "contact_email": contact.email,
                "summary_type": summary_type,
                "summary": summary_content["content"],
                "talking_points": summary_content.get("talking_points", []),
                "relationship_insights": summary_content.get("relationship_insights", {}),
                "last_interaction": contact_data.get("last_interaction_date"),
                "interaction_count": contact_data.get("interaction_count", 0),
                "relationship_strength": contact_data.get("relationship_strength", 0.0),
                "generated_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(
                    hours=self.cache_duration_hours[summary_type]
                )).isoformat(),
                "cached": False,
                "model_used": summary_content.get("model_used", "gpt-3.5-turbo"),
                "token_usage": summary_content.get("token_usage")
            }
            
            # Cache the summary
            await self._cache_summary(contact_id, user_id, summary_type, summary)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating contact summary: {e}")
            raise ContactSummarizationError(f"Failed to generate summary: {str(e)}")
    
    async def get_cached_summary(
        self,
        contact_id: UUID,
        user_id: UUID,
        summary_type: str = SummaryType.COMPREHENSIVE,
        max_age_hours: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached summary if available and not expired."""
        try:
            max_age = max_age_hours or self.cache_duration_hours[summary_type]
            cached = await self._get_cached_summary(
                contact_id, user_id, summary_type, max_age
            )
            if cached:
                cached["cached"] = True
            return cached
        except Exception as e:
            logger.warning(f"Error retrieving cached summary: {e}")
            return None
    
    async def generate_pre_meeting_summary(
        self,
        contact_id: UUID,
        user_id: UUID,
        meeting_context: str,
        meeting_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate a specialized summary for upcoming meetings."""
        try:
            # Always refresh for pre-meeting summaries
            summary = await self.generate_contact_summary(
                contact_id=contact_id,
                user_id=user_id,
                summary_type=SummaryType.PRE_MEETING,
                meeting_context=meeting_context,
                force_refresh=True
            )
            
            # Add meeting-specific metadata
            summary["meeting_context"] = meeting_context
            summary["meeting_date"] = meeting_date.isoformat() if meeting_date else None
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating pre-meeting summary: {e}")
            raise ContactSummarizationError(f"Failed to generate pre-meeting summary: {str(e)}")
    
    async def update_summary_on_interaction(
        self,
        contact_id: UUID,
        user_id: UUID,
        interaction_data: Dict[str, Any]
    ) -> bool:
        """Update contact summary when new interaction occurs."""
        try:
            # Invalidate existing summaries to force refresh
            await self._invalidate_cached_summaries(contact_id, user_id)
            
            # Log the interaction trigger
            logger.info(f"Summary cache invalidated for contact {contact_id} due to new interaction")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating summary on interaction: {e}")
            return False
    
    async def generate_batch_summaries(
        self,
        contact_ids: List[UUID],
        user_id: UUID,
        summary_type: str = SummaryType.BRIEF,
        max_contacts: int = 50
    ) -> List[Dict[str, Any]]:
        """Generate summaries for multiple contacts efficiently."""
        try:
            # Limit batch size for performance
            limited_contacts = contact_ids[:max_contacts]
            summaries = []
            
            for contact_id in limited_contacts:
                try:
                    summary = await self.generate_contact_summary(
                        contact_id=contact_id,
                        user_id=user_id,
                        summary_type=summary_type,
                        force_refresh=False  # Use cache for batch operations
                    )
                    summaries.append(summary)
                except Exception as e:
                    logger.warning(f"Failed to generate summary for contact {contact_id}: {e}")
                    # Continue with other contacts
                    continue
            
            return summaries
            
        except Exception as e:
            logger.error(f"Error generating batch summaries: {e}")
            raise ContactSummarizationError(f"Failed to generate batch summaries: {str(e)}")
    
    def _get_contact_with_validation(self, contact_id: UUID, user_id: UUID) -> Contact:
        """Get contact and validate user access."""
        contact = self.db.query(Contact).filter(
            and_(Contact.id == contact_id, Contact.user_id == user_id)
        ).first()
        
        if not contact:
            raise ContactSummarizationError(f"Contact {contact_id} not found or access denied")
        
        return contact
    
    async def _gather_contact_data(self, contact_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """Gather all relevant data for contact summarization."""
        try:
            # Get contact details
            contact = self.db.query(Contact).filter(
                and_(Contact.id == contact_id, Contact.user_id == user_id)
            ).first()
            
            # Get recent interactions
            interactions = self.db.query(Interaction).filter(
                and_(
                    Interaction.contact_id == contact_id,
                    Interaction.user_id == user_id
                )
            ).order_by(desc(Interaction.interaction_date)).limit(20).all()
            
            # Get conversation threads from threading service
            threads = await self.threading_service.build_conversation_threads(
                user_id=str(user_id),
                contact_id=str(contact_id),
                days_back=90
            )
            
            # Compile data
            contact_data = {
                "contact": {
                    "id": str(contact.id),
                    "name": contact.full_name,
                    "email": contact.email,
                    "phone": contact.phone,
                    "company": contact.company,
                    "job_title": contact.job_title,
                    "source": contact.contact_source,
                    "relationship_strength": float(contact.relationship_strength) if contact.relationship_strength else 0.0,
                    "tags": contact.tags or [],
                    "notes": contact.notes,
                    "created_at": contact.created_at.isoformat() if contact.created_at else None,
                    "last_interaction_at": contact.last_interaction_at.isoformat() if contact.last_interaction_at else None
                },
                "interactions": [
                    {
                        "id": str(interaction.id),
                        "type": interaction.interaction_type,
                        "date": interaction.interaction_date.isoformat(),
                        "summary": interaction.content_summary or interaction.subject or "No summary available",
                        "source": interaction.source_platform,
                        "metadata": interaction.platform_metadata or {}
                    }
                    for interaction in interactions
                ],
                "conversation_threads": [
                    {
                        "id": thread.thread_id,
                        "subject": thread.subject_themes[0] if thread.subject_themes else "General Conversation",
                        "message_count": thread.total_interactions,
                        "last_message_date": thread.end_date.isoformat(),
                        "thread_summary": getattr(thread, 'thread_summary', None),
                        "participant_emails": []  # Extract from interactions if needed
                    }
                    for thread in threads[:5]  # Limit to 5 threads
                ],
                "stats": {
                    "interaction_count": len(interactions),
                    "last_interaction_date": interactions[0].interaction_date.isoformat() if interactions else None,
                    "relationship_strength": float(contact.relationship_strength) if contact.relationship_strength else 0.0,
                    "days_since_last_contact": (
                        (datetime.utcnow() - interactions[0].interaction_date).days
                        if interactions else None
                    )
                }
            }
            
            return contact_data
            
        except Exception as e:
            logger.error(f"Error gathering contact data: {e}")
            raise ContactSummarizationError(f"Failed to gather contact data: {str(e)}")
    
    async def _generate_summary_content(
        self,
        contact_data: Dict[str, Any],
        summary_type: str,
        meeting_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate the actual summary content using AI."""
        try:
            # Select appropriate prompt based on summary type
            prompt = self._build_prompt(contact_data, summary_type, meeting_context)
            
            # Use AI assistant service for generation
            response = await self.ai_service.generate_message(
                message_type="contact_summary",
                recipient_context=json.dumps(contact_data["contact"]),
                message_context=prompt,
                user_id=str(contact_data["contact"]["id"]),
                tone="professional",
                force_refresh=True
            )
            
            # Parse the response to extract structured data
            parsed_content = self._parse_summary_response(response.content, summary_type)
            
            return {
                "content": parsed_content["summary"],
                "talking_points": parsed_content.get("talking_points", []),
                "relationship_insights": parsed_content.get("insights", {}),
                "model_used": response.model,
                "token_usage": response.usage.to_dict() if response.usage else None
            }
            
        except Exception as e:
            logger.error(f"Error generating summary content: {e}")
            raise ContactSummarizationError(f"Failed to generate summary content: {str(e)}")
    
    def _build_prompt(
        self,
        contact_data: Dict[str, Any],
        summary_type: str,
        meeting_context: Optional[str] = None
    ) -> str:
        """Build the appropriate prompt for the summary type."""
        contact = contact_data["contact"]
        interactions = contact_data["interactions"]
        threads = contact_data["conversation_threads"]
        stats = contact_data["stats"]
        
        base_context = f"""
Contact: {contact['name']} ({contact['email']})
Company: {contact.get('company', 'Unknown')}
Job Title: {contact.get('job_title', 'Unknown')}
Relationship Strength: {stats['relationship_strength']}/10
Total Interactions: {stats['interaction_count']}
Last Contact: {stats.get('last_interaction_date', 'Unknown')}
"""
        
        if summary_type == SummaryType.COMPREHENSIVE:
            return f"""
{base_context}

Recent Interactions:
{self._format_interactions(interactions[:10])}

Conversation Threads:
{self._format_threads(threads[:3])}

Generate a comprehensive summary of this contact including:
1. Professional background and current role
2. Relationship history and key interactions
3. Communication patterns and preferences
4. Key topics of mutual interest
5. Relationship strength assessment
6. Recommended next steps

Format as JSON with keys: summary, talking_points, insights
"""
        
        elif summary_type == SummaryType.BRIEF:
            return f"""
{base_context}

Recent Activity:
{self._format_interactions(interactions[:5])}

Generate a brief contact summary including:
1. Who they are professionally
2. Recent interaction highlights
3. Current relationship status
4. 2-3 key talking points

Format as JSON with keys: summary, talking_points
"""
        
        elif summary_type == SummaryType.PRE_MEETING:
            return f"""
{base_context}

Meeting Context: {meeting_context or 'General meeting'}

Recent Interactions:
{self._format_interactions(interactions[:5])}

Recent Conversations:
{self._format_threads(threads[:2])}

Generate a pre-meeting summary including:
1. Key background information
2. Recent conversation topics
3. Potential talking points for the meeting
4. Any follow-ups or commitments to address
5. Meeting-specific preparation notes

Format as JSON with keys: summary, talking_points, meeting_notes
"""
        
        elif summary_type == SummaryType.RELATIONSHIP_STATUS:
            return f"""
{base_context}

Communication History:
{self._format_interactions(interactions)}

Assess the relationship status including:
1. Current relationship health (strong/moderate/weak/cold)
2. Communication frequency trends
3. Engagement level analysis
4. Risk factors (going cold, decreased interaction)
5. Recommended actions to maintain/strengthen relationship

Format as JSON with keys: summary, insights, recommendations
"""
        
        elif summary_type == SummaryType.UPDATES:
            days_back = 30
            return f"""
{base_context}

Recent Updates (Last {days_back} days):
{self._format_interactions(interactions[:10])}

Summarize what's new with this contact:
1. Recent interactions and conversations
2. Any changes in communication patterns
3. New developments or topics discussed
4. Action items or follow-ups needed

Format as JSON with keys: summary, recent_changes, action_items
"""
        
        return f"{base_context}\n\nGenerate a professional summary of this contact."
    
    def _format_interactions(self, interactions: List[Dict[str, Any]]) -> str:
        """Format interactions for prompt inclusion."""
        if not interactions:
            return "No recent interactions found."
        
        formatted = []
        for interaction in interactions:
            formatted.append(
                f"- {interaction['date'][:10]} ({interaction['type']}): {interaction['summary']}"
            )
        
        return "\n".join(formatted)
    
    def _format_threads(self, threads: List[Dict[str, Any]]) -> str:
        """Format conversation threads for prompt inclusion."""
        if not threads:
            return "No recent conversation threads found."
        
        formatted = []
        for thread in threads:
            formatted.append(
                f"- {thread['subject']} ({thread['message_count']} messages, last: {thread['last_message_date'][:10]})"
            )
        
        return "\n".join(formatted)
    
    def _parse_summary_response(self, response: str, summary_type: str) -> Dict[str, Any]:
        """Parse AI response into structured format."""
        try:
            # Try to parse as JSON first
            parsed = json.loads(response)
            return parsed
        except json.JSONDecodeError:
            # Fallback to plain text parsing
            return {
                "summary": response,
                "talking_points": [],
                "insights": {}
            }
    
    async def _get_cached_summary(
        self,
        contact_id: UUID,
        user_id: UUID,
        summary_type: str,
        max_age_hours: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached summary if available."""
        # This would integrate with Redis cache
        # For now, return None to always generate fresh
        return None
    
    async def _cache_summary(
        self,
        contact_id: UUID,
        user_id: UUID,
        summary_type: str,
        summary: Dict[str, Any]
    ) -> bool:
        """Cache the generated summary."""
        # This would store in Redis cache
        # For now, just log the caching attempt
        logger.info(f"Caching summary for contact {contact_id}, type {summary_type}")
        return True
    
    async def _invalidate_cached_summaries(self, contact_id: UUID, user_id: UUID) -> bool:
        """Invalidate all cached summaries for a contact."""
        # This would clear Redis cache entries
        logger.info(f"Invalidating cached summaries for contact {contact_id}")
        return True
    
    def _generate_cache_key(self, contact_id: UUID, user_id: UUID, summary_type: str) -> str:
        """Generate cache key for summary storage."""
        return f"contact_summary:{user_id}:{contact_id}:{summary_type}" 