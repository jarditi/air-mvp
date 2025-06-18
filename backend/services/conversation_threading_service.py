"""
Cross-Platform Conversation Threading Service

This service implements Task 3.6.1: Cross-Platform Conversation Threading.
It unifies conversations across email, calendar, LinkedIn with smart thread merging
and context linking, building on existing email threading foundation.

Key Features:
- Unified conversation assembly across multiple platforms
- Smart thread merging based on temporal, semantic, and participant overlap
- Context linking between related interactions
- Thread lifecycle management and optimization
- Cross-platform conversation analytics
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from collections import defaultdict, Counter
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from uuid import UUID, uuid4
import re
from difflib import SequenceMatcher

from models.orm.interaction import Interaction
from models.orm.contact import Contact
from models.orm.user import User
from services.ai_assistant import AIAssistantService
from lib.llm_client import LLMUsageType

logger = logging.getLogger(__name__)


@dataclass
class ConversationThread:
    """Unified conversation thread across platforms"""
    thread_id: str
    contact_id: str
    user_id: str
    platforms: Set[str]  # Set of platforms in this thread
    interactions: List[Dict[str, Any]]  # Ordered list of interactions
    start_date: datetime
    end_date: datetime
    total_interactions: int
    thread_depth: int
    subject_themes: List[str]  # Common subjects/themes
    dominant_platform: str  # Platform with most interactions
    participant_count: int
    thread_type: str  # 'ongoing', 'completed', 'dormant', 'sporadic'
    context_score: float  # How well-connected the interactions are
    thread_summary: Optional[str] = None


@dataclass
class ThreadMergeCandidate:
    """Candidate for thread merging"""
    thread_a: ConversationThread
    thread_b: ConversationThread
    merge_confidence: float
    merge_strategy: str  # 'temporal_overlap', 'subject_similarity', 'participant_match', 'context_link'
    evidence: Dict[str, Any]
    recommended_action: str  # 'auto_merge', 'manual_review', 'separate'


@dataclass
class ConversationContext:
    """Context information linking interactions"""
    interaction_id: str
    related_interactions: List[str]
    context_type: str  # 'follow_up', 'preparation', 'outcome', 'reference'
    confidence_score: float
    evidence: Dict[str, Any]


class ConversationThreadingService:
    """
    Service for cross-platform conversation threading and context linking
    """
    
    # Configuration constants
    TEMPORAL_WINDOW_HOURS = 48  # Hours to consider for temporal linking
    SUBJECT_SIMILARITY_THRESHOLD = 0.7  # Minimum similarity for subject linking
    PARTICIPANT_OVERLAP_THRESHOLD = 0.5  # Minimum participant overlap for merging
    AUTO_MERGE_CONFIDENCE_THRESHOLD = 0.8  # Confidence threshold for auto-merge
    MANUAL_REVIEW_CONFIDENCE_THRESHOLD = 0.6  # Confidence threshold for manual review
    
    # Platform priorities for dominant platform determination
    PLATFORM_PRIORITIES = {
        'email': 3,
        'meeting': 2,
        'calendar': 2,
        'linkedin': 1,
        'manual': 1
    }
    
    def __init__(self, db: Session):
        """
        Initialize conversation threading service
        
        Args:
            db: Database session
        """
        self.db = db
        self.ai_assistant = AIAssistantService(db)
        
    async def build_conversation_threads(
        self,
        user_id: str,
        contact_id: Optional[str] = None,
        days_back: int = 90,
        include_platforms: Optional[List[str]] = None,
        force_rebuild: bool = False
    ) -> List[ConversationThread]:
        """
        Build unified conversation threads for a user or specific contact
        
        Args:
            user_id: User ID
            contact_id: Optional contact ID to filter threads
            days_back: Number of days back to analyze
            include_platforms: Optional list of platforms to include
            force_rebuild: Force rebuild of all threads
            
        Returns:
            List of conversation threads
        """
        try:
            logger.info(f"Building conversation threads for user {user_id}")
            
            # Get interactions from database
            interactions = await self._fetch_interactions(
                user_id=user_id,
                contact_id=contact_id,
                days_back=days_back,
                include_platforms=include_platforms
            )
            
            if not interactions:
                return []
            
            # Group interactions by contact
            contact_interactions = defaultdict(list)
            for interaction in interactions:
                contact_interactions[str(interaction.contact_id)].append(interaction)
            
            # Build threads for each contact
            all_threads = []
            for contact_id, contact_ints in contact_interactions.items():
                threads = await self._build_contact_threads(contact_id, contact_ints)
                all_threads.extend(threads)
            
            # Find and process thread merge candidates
            merge_candidates = await self._find_thread_merge_candidates(all_threads)
            merged_threads = await self._process_thread_merges(all_threads, merge_candidates)
            
            # Sort threads by recency and importance
            sorted_threads = sorted(
                merged_threads,
                key=lambda t: (t.end_date, t.context_score),
                reverse=True
            )
            
            logger.info(f"Built {len(sorted_threads)} conversation threads")
            return sorted_threads
            
        except Exception as e:
            logger.error(f"Failed to build conversation threads: {e}")
            raise
    
    async def _fetch_interactions(
        self,
        user_id: str,
        contact_id: Optional[str] = None,
        days_back: int = 90,
        include_platforms: Optional[List[str]] = None
    ) -> List[Interaction]:
        """
        Fetch interactions from database with filtering
        
        Args:
            user_id: User ID
            contact_id: Optional contact ID filter
            days_back: Number of days back
            include_platforms: Optional platform filter
            
        Returns:
            List of interactions
        """
        # Build query
        query = self.db.query(Interaction).filter(
            Interaction.user_id == user_id
        )
        
        # Add contact filter
        if contact_id:
            query = query.filter(Interaction.contact_id == contact_id)
        
        # Add date filter
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        query = query.filter(Interaction.interaction_date >= cutoff_date)
        
        # Add platform filter
        if include_platforms:
            query = query.filter(Interaction.source_platform.in_(include_platforms))
        
        # Order by date
        query = query.order_by(Interaction.interaction_date.asc())
        
        return query.all()
    
    async def _build_contact_threads(
        self,
        contact_id: str,
        interactions: List[Interaction]
    ) -> List[ConversationThread]:
        """
        Build conversation threads for a specific contact
        
        Args:
            contact_id: Contact ID
            interactions: List of interactions with the contact
            
        Returns:
            List of conversation threads
        """
        if not interactions:
            return []
        
        # Sort interactions by date
        sorted_interactions = sorted(interactions, key=lambda x: x.interaction_date)
        
        # Group interactions into threads using multiple strategies
        thread_groups = await self._group_interactions_into_threads(sorted_interactions)
        
        # Convert groups to ConversationThread objects
        threads = []
        for i, group in enumerate(thread_groups):
            thread = await self._create_conversation_thread(
                thread_id=f"{contact_id}_thread_{i}",
                contact_id=contact_id,
                interactions=group
            )
            threads.append(thread)
        
        return threads
    
    async def _group_interactions_into_threads(
        self,
        interactions: List[Interaction]
    ) -> List[List[Interaction]]:
        """
        Group interactions into thread candidates using multiple strategies
        
        Args:
            interactions: Sorted list of interactions
            
        Returns:
            List of interaction groups (threads)
        """
        if not interactions:
            return []
        
        thread_groups = []
        current_thread = [interactions[0]]
        
        for i in range(1, len(interactions)):
            current_interaction = interactions[i]
            prev_interaction = interactions[i-1]
            
            # Check if this interaction should be in the same thread
            should_merge = await self._should_merge_into_thread(
                current_interaction, prev_interaction, current_thread
            )
            
            if should_merge:
                current_thread.append(current_interaction)
            else:
                # Start new thread
                thread_groups.append(current_thread)
                current_thread = [current_interaction]
        
        # Add the last thread
        thread_groups.append(current_thread)
        
        return thread_groups
    
    async def _should_merge_into_thread(
        self,
        current_interaction: Interaction,
        prev_interaction: Interaction,
        current_thread: List[Interaction]
    ) -> bool:
        """
        Determine if current interaction should merge into the existing thread
        
        Args:
            current_interaction: Current interaction
            prev_interaction: Previous interaction
            current_thread: Current thread interactions
            
        Returns:
            True if should merge
        """
        # Strategy 1: Temporal proximity
        time_diff = current_interaction.interaction_date - prev_interaction.interaction_date
        if time_diff <= timedelta(hours=self.TEMPORAL_WINDOW_HOURS):
            return True
        
        # Strategy 2: Subject similarity (for emails)
        if (current_interaction.subject and prev_interaction.subject and
            current_interaction.interaction_type == 'email' and 
            prev_interaction.interaction_type == 'email'):
            
            similarity = self._calculate_subject_similarity(
                current_interaction.subject, prev_interaction.subject
            )
            if similarity >= self.SUBJECT_SIMILARITY_THRESHOLD:
                return True
        
        # Strategy 3: Meeting follow-up pattern
        if await self._is_meeting_followup_pattern(current_interaction, current_thread):
            return True
        
        # Strategy 4: External ID linking (for email threads)
        if (current_interaction.platform_metadata and prev_interaction.platform_metadata and
            current_interaction.source_platform == 'gmail' and prev_interaction.source_platform == 'gmail'):
            
            curr_thread_id = current_interaction.platform_metadata.get('thread_id')
            prev_thread_id = prev_interaction.platform_metadata.get('thread_id')
            if curr_thread_id and prev_thread_id and curr_thread_id == prev_thread_id:
                return True
        
        return False
    
    def _calculate_subject_similarity(self, subject1: str, subject2: str) -> float:
        """
        Calculate similarity between two subjects
        
        Args:
            subject1: First subject
            subject2: Second subject
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Normalize subjects
        def normalize_subject(subject):
            # Remove Re:, Fwd:, etc.
            normalized = re.sub(r'^(re|fwd|fw):\s*', '', subject.lower().strip())
            # Remove extra whitespace
            normalized = re.sub(r'\s+', ' ', normalized)
            return normalized
        
        norm1 = normalize_subject(subject1)
        norm2 = normalize_subject(subject2)
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    async def _is_meeting_followup_pattern(
        self,
        current_interaction: Interaction,
        thread_interactions: List[Interaction]
    ) -> bool:
        """
        Check if current interaction follows a meeting follow-up pattern
        
        Args:
            current_interaction: Current interaction
            thread_interactions: Interactions in current thread
            
        Returns:
            True if this appears to be a meeting follow-up
        """
        # Look for meeting -> email pattern within 24 hours
        for thread_int in thread_interactions:
            if thread_int.interaction_type in ['meeting', 'calendar']:
                time_diff = current_interaction.interaction_date - thread_int.interaction_date
                if (0 <= time_diff.total_seconds() <= 24 * 3600 and 
                    current_interaction.interaction_type == 'email'):
                    
                    # Check for follow-up keywords in subject
                    if current_interaction.subject:
                        followup_keywords = [
                            'follow', 'recap', 'summary', 'action', 'next steps',
                            'thank you', 'thanks for', 'meeting', 'discussed'
                        ]
                        subject_lower = current_interaction.subject.lower()
                        if any(keyword in subject_lower for keyword in followup_keywords):
                            return True
        
        return False
    
    async def _create_conversation_thread(
        self,
        thread_id: str,
        contact_id: str,
        interactions: List[Interaction]
    ) -> ConversationThread:
        """
        Create a ConversationThread object from interactions
        
        Args:
            thread_id: Thread identifier
            contact_id: Contact ID
            interactions: List of interactions in the thread
            
        Returns:
            ConversationThread object
        """
        if not interactions:
            raise ValueError("Cannot create thread from empty interactions")
        
        # Sort interactions by date
        sorted_interactions = sorted(interactions, key=lambda x: x.interaction_date)
        
        # Extract basic information
        start_date = sorted_interactions[0].interaction_date
        end_date = sorted_interactions[-1].interaction_date
        platforms = set(int.source_platform for int in interactions if int.source_platform)
        user_id = str(sorted_interactions[0].user_id)
        
        # Calculate thread metrics
        total_interactions = len(interactions)
        thread_depth = self._calculate_thread_depth(interactions)
        subject_themes = self._extract_subject_themes(interactions)
        dominant_platform = self._determine_dominant_platform(interactions)
        participant_count = self._count_unique_participants(interactions)
        thread_type = self._classify_thread_type(interactions)
        context_score = await self._calculate_context_score(interactions)
        
        # Convert interactions to serializable format
        interaction_dicts = []
        for interaction in sorted_interactions:
            interaction_dict = {
                'id': str(interaction.id),
                'interaction_type': interaction.interaction_type,
                'direction': interaction.direction,
                'subject': interaction.subject,
                'interaction_date': interaction.interaction_date.isoformat(),
                'source_platform': interaction.source_platform,
                'duration_minutes': interaction.duration_minutes,
                'sentiment_score': float(interaction.sentiment_score) if interaction.sentiment_score else None,
                'meeting_attendees': interaction.meeting_attendees or [],
                'platform_metadata': interaction.platform_metadata or {}
            }
            interaction_dicts.append(interaction_dict)
        
        return ConversationThread(
            thread_id=thread_id,
            contact_id=contact_id,
            user_id=user_id,
            platforms=platforms,
            interactions=interaction_dicts,
            start_date=start_date,
            end_date=end_date,
            total_interactions=total_interactions,
            thread_depth=thread_depth,
            subject_themes=subject_themes,
            dominant_platform=dominant_platform,
            participant_count=participant_count,
            thread_type=thread_type,
            context_score=context_score
        )
    
    def _calculate_thread_depth(self, interactions: List[Interaction]) -> int:
        """Calculate thread depth based on back-and-forth patterns"""
        if len(interactions) <= 1:
            return 1
        
        depth = 1
        last_direction = interactions[0].direction
        
        for interaction in interactions[1:]:
            if interaction.direction != last_direction and interaction.direction != 'mutual':
                depth += 1
            last_direction = interaction.direction
        
        return depth
    
    def _extract_subject_themes(self, interactions: List[Interaction]) -> List[str]:
        """Extract common themes from interaction subjects"""
        subjects = [int.subject for int in interactions if int.subject]
        if not subjects:
            return []
        
        # Simple keyword extraction
        all_words = []
        for subject in subjects:
            # Remove common prefixes and split into words
            clean_subject = re.sub(r'^(re|fwd|fw):\s*', '', subject.lower())
            words = re.findall(r'\b\w{3,}\b', clean_subject)
            all_words.extend(words)
        
        # Count word frequency and return top themes
        word_counts = Counter(all_words)
        common_words = ['meeting', 'call', 'project', 'team', 'update', 'follow', 'discussion']
        
        themes = []
        for word, count in word_counts.most_common(5):
            if word not in common_words and count > 1:
                themes.append(word)
        
        return themes[:3]  # Return top 3 themes
    
    def _determine_dominant_platform(self, interactions: List[Interaction]) -> str:
        """Determine the dominant platform in the thread"""
        platform_counts = Counter(int.source_platform for int in interactions if int.source_platform)
        
        if not platform_counts:
            return 'unknown'
        
        # Weight by platform priority
        weighted_scores = {}
        for platform, count in platform_counts.items():
            priority = self.PLATFORM_PRIORITIES.get(platform, 1)
            weighted_scores[platform] = count * priority
        
        return max(weighted_scores.items(), key=lambda x: x[1])[0]
    
    def _count_unique_participants(self, interactions: List[Interaction]) -> int:
        """Count unique participants across all interactions"""
        participants = set()
        
        for interaction in interactions:
            if interaction.meeting_attendees:
                participants.update(interaction.meeting_attendees)
        
        # Add contact as participant
        participants.add(str(interactions[0].contact_id))
        
        return len(participants)
    
    def _classify_thread_type(self, interactions: List[Interaction]) -> str:
        """Classify the thread type based on patterns"""
        if not interactions:
            return 'unknown'
        
        time_span = (interactions[-1].interaction_date - interactions[0].interaction_date).days
        interaction_count = len(interactions)
        
        # Recent activity (last 7 days)
        recent_interactions = [
            int for int in interactions 
            if (datetime.now(timezone.utc) - int.interaction_date).days <= 7
        ]
        
        if recent_interactions:
            return 'ongoing'
        elif time_span <= 1 and interaction_count >= 3:
            return 'completed'  # Intensive short conversation
        elif time_span >= 30 and interaction_count >= 5:
            return 'sporadic'  # Spread out over time
        else:
            return 'dormant'
    
    async def _calculate_context_score(self, interactions: List[Interaction]) -> float:
        """Calculate how well-connected the interactions are contextually"""
        if len(interactions) <= 1:
            return 0.5
        
        score = 0.0
        factors = 0
        
        # Factor 1: Temporal consistency
        if len(interactions) >= 3:
            intervals = []
            for i in range(1, len(interactions)):
                interval = (interactions[i].interaction_date - interactions[i-1].interaction_date).total_seconds()
                intervals.append(interval)
            
            if intervals:
                import statistics
                mean_interval = statistics.mean(intervals)
                if mean_interval > 0:
                    std_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0
                    cv = std_interval / mean_interval
                    temporal_score = max(0, 1 - cv)
                    score += temporal_score
                    factors += 1
        
        # Factor 2: Bidirectional communication
        directions = [int.direction for int in interactions]
        unique_directions = set(directions)
        if len(unique_directions) > 1:
            score += 0.8
        factors += 1
        
        # Factor 3: Platform consistency or logical progression
        platforms = [int.source_platform for int in interactions if int.source_platform]
        if len(set(platforms)) == 1:
            score += 0.6  # Consistent platform
        elif 'email' in platforms and 'meeting' in platforms:
            score += 0.8  # Email + meeting is natural progression
        factors += 1
        
        return score / factors if factors > 0 else 0.5
    
    async def _find_thread_merge_candidates(
        self,
        threads: List[ConversationThread]
    ) -> List[ThreadMergeCandidate]:
        """Find candidate thread pairs for merging"""
        candidates = []
        
        # Compare threads from the same contact
        contact_threads = defaultdict(list)
        for thread in threads:
            contact_threads[thread.contact_id].append(thread)
        
        for contact_id, contact_thread_list in contact_threads.items():
            if len(contact_thread_list) < 2:
                continue
            
            for i in range(len(contact_thread_list)):
                for j in range(i + 1, len(contact_thread_list)):
                    thread_a = contact_thread_list[i]
                    thread_b = contact_thread_list[j]
                    
                    candidate = await self._evaluate_thread_merge(thread_a, thread_b)
                    if candidate:
                        candidates.append(candidate)
        
        return candidates
    
    async def _evaluate_thread_merge(
        self,
        thread_a: ConversationThread,
        thread_b: ConversationThread
    ) -> Optional[ThreadMergeCandidate]:
        """Evaluate if two threads should be merged"""
        evidence = {}
        confidence_factors = []
        merge_strategy = 'none'
        
        # Ensure thread_a is earlier than thread_b
        if thread_a.start_date > thread_b.start_date:
            thread_a, thread_b = thread_b, thread_a
        
        # Factor 1: Temporal overlap or proximity
        time_gap = thread_b.start_date - thread_a.end_date
        if time_gap <= timedelta(hours=self.TEMPORAL_WINDOW_HOURS):
            temporal_score = max(0, 1 - (time_gap.total_seconds() / (self.TEMPORAL_WINDOW_HOURS * 3600)))
            confidence_factors.append(('temporal_overlap', temporal_score))
            evidence['time_gap_hours'] = time_gap.total_seconds() / 3600
            if temporal_score > 0.5:
                merge_strategy = 'temporal_overlap'
        
        # Factor 2: Subject theme similarity
        if thread_a.subject_themes and thread_b.subject_themes:
            common_themes = set(thread_a.subject_themes) & set(thread_b.subject_themes)
            if common_themes:
                theme_score = len(common_themes) / max(len(thread_a.subject_themes), len(thread_b.subject_themes))
                confidence_factors.append(('subject_similarity', theme_score))
                evidence['common_themes'] = list(common_themes)
                if theme_score > 0.5:
                    merge_strategy = 'subject_similarity'
        
        # Factor 3: Platform transition patterns
        if self._is_natural_platform_transition(thread_a, thread_b):
            transition_score = 0.7
            confidence_factors.append(('platform_transition', transition_score))
            evidence['platform_transition'] = f"{thread_a.dominant_platform} -> {thread_b.dominant_platform}"
            merge_strategy = 'context_link'
        
        # Calculate overall confidence
        if not confidence_factors:
            return None
        
        total_confidence = sum(score for _, score in confidence_factors)
        avg_confidence = total_confidence / len(confidence_factors)
        
        # Determine recommended action
        if avg_confidence >= self.AUTO_MERGE_CONFIDENCE_THRESHOLD:
            recommended_action = 'auto_merge'
        elif avg_confidence >= self.MANUAL_REVIEW_CONFIDENCE_THRESHOLD:
            recommended_action = 'manual_review'
        else:
            recommended_action = 'separate'
        
        return ThreadMergeCandidate(
            thread_a=thread_a,
            thread_b=thread_b,
            merge_confidence=avg_confidence,
            merge_strategy=merge_strategy,
            evidence=evidence,
            recommended_action=recommended_action
        )
    
    def _is_natural_platform_transition(
        self,
        thread_a: ConversationThread,
        thread_b: ConversationThread
    ) -> bool:
        """Check if platform transition between threads is natural"""
        natural_transitions = [
            ('email', 'meeting'),
            ('meeting', 'email'),
            ('email', 'calendar'),
            ('calendar', 'email')
        ]
        
        transition = (thread_a.dominant_platform, thread_b.dominant_platform)
        return transition in natural_transitions
    
    async def _process_thread_merges(
        self,
        threads: List[ConversationThread],
        candidates: List[ThreadMergeCandidate]
    ) -> List[ConversationThread]:
        """Process thread merge candidates and return merged threads"""
        # Sort candidates by confidence (highest first)
        sorted_candidates = sorted(candidates, key=lambda c: c.merge_confidence, reverse=True)
        
        # Track which threads have been merged
        merged_thread_ids = set()
        result_threads = []
        
        # Process auto-merge candidates
        for candidate in sorted_candidates:
            if candidate.recommended_action == 'auto_merge':
                if (candidate.thread_a.thread_id not in merged_thread_ids and
                    candidate.thread_b.thread_id not in merged_thread_ids):
                    
                    # Merge the threads
                    merged_thread = await self._merge_threads(candidate.thread_a, candidate.thread_b)
                    result_threads.append(merged_thread)
                    
                    # Mark as merged
                    merged_thread_ids.add(candidate.thread_a.thread_id)
                    merged_thread_ids.add(candidate.thread_b.thread_id)
                    
                    logger.info(f"Auto-merged threads {candidate.thread_a.thread_id} and {candidate.thread_b.thread_id}")
        
        # Add remaining unmerged threads
        for thread in threads:
            if thread.thread_id not in merged_thread_ids:
                result_threads.append(thread)
        
        return result_threads
    
    async def _merge_threads(
        self,
        thread_a: ConversationThread,
        thread_b: ConversationThread
    ) -> ConversationThread:
        """Merge two conversation threads"""
        # Combine interactions and sort by date
        all_interactions = thread_a.interactions + thread_b.interactions
        sorted_interactions = sorted(all_interactions, key=lambda x: x['interaction_date'])
        
        # Create merged thread
        merged_thread = ConversationThread(
            thread_id=f"{thread_a.thread_id}_merged_{thread_b.thread_id}",
            contact_id=thread_a.contact_id,
            user_id=thread_a.user_id,
            platforms=thread_a.platforms | thread_b.platforms,
            interactions=sorted_interactions,
            start_date=min(thread_a.start_date, thread_b.start_date),
            end_date=max(thread_a.end_date, thread_b.end_date),
            total_interactions=thread_a.total_interactions + thread_b.total_interactions,
            thread_depth=max(thread_a.thread_depth, thread_b.thread_depth) + 1,
            subject_themes=list(set(thread_a.subject_themes + thread_b.subject_themes)),
            dominant_platform=self._choose_dominant_platform(thread_a, thread_b),
            participant_count=max(thread_a.participant_count, thread_b.participant_count),
            thread_type=self._merge_thread_types(thread_a.thread_type, thread_b.thread_type),
            context_score=(thread_a.context_score + thread_b.context_score) / 2
        )
        
        return merged_thread
    
    def _choose_dominant_platform(
        self,
        thread_a: ConversationThread,
        thread_b: ConversationThread
    ) -> str:
        """Choose dominant platform for merged thread"""
        platform_a_priority = self.PLATFORM_PRIORITIES.get(thread_a.dominant_platform, 1)
        platform_b_priority = self.PLATFORM_PRIORITIES.get(thread_b.dominant_platform, 1)
        
        if platform_a_priority > platform_b_priority:
            return thread_a.dominant_platform
        elif platform_b_priority > platform_a_priority:
            return thread_b.dominant_platform
        else:
            return thread_a.dominant_platform if thread_a.total_interactions >= thread_b.total_interactions else thread_b.dominant_platform
    
    def _merge_thread_types(self, type_a: str, type_b: str) -> str:
        """Merge thread types with priority logic"""
        type_priority = {
            'ongoing': 4,
            'completed': 3,
            'sporadic': 2,
            'dormant': 1
        }
        
        priority_a = type_priority.get(type_a, 0)
        priority_b = type_priority.get(type_b, 0)
        
        return type_a if priority_a >= priority_b else type_b
    
    async def generate_thread_summary(
        self,
        thread: ConversationThread
    ) -> str:
        """Generate AI-powered summary for a conversation thread"""
        try:
            # Prepare context for AI
            context_parts = [
                f"Conversation thread with {thread.total_interactions} interactions",
                f"Platforms: {', '.join(thread.platforms)}",
                f"Duration: {thread.start_date.date()} to {thread.end_date.date()}",
                f"Thread type: {thread.thread_type}"
            ]
            
            if thread.subject_themes:
                context_parts.append(f"Main topics: {', '.join(thread.subject_themes)}")
            
            # Extract key interaction details
            interaction_summaries = []
            for interaction in thread.interactions[-5:]:  # Last 5 interactions
                summary = f"{interaction['interaction_date'][:10]} - {interaction['interaction_type']}"
                if interaction['subject']:
                    summary += f": {interaction['subject'][:50]}"
                interaction_summaries.append(summary)
            
            prompt = f"""
            Summarize this conversation thread in 2-3 sentences:
            
            Context: {' | '.join(context_parts)}
            
            Recent interactions:
            {chr(10).join(interaction_summaries)}
            
            Focus on the relationship progression and key outcomes.
            """
            
            response = await self.ai_assistant.generate_with_cache(
                prompt=prompt,
                user_id=thread.user_id,
                request_type='thread_summary',
                usage_type=LLMUsageType.CONTENT_ANALYSIS,
                temperature=0.5,
                max_tokens=150
            )
            
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate thread summary: {e}")
            return f"Conversation thread with {thread.total_interactions} interactions across {len(thread.platforms)} platforms" 