"""
Contact Quality Scoring Service

This service implements a comprehensive contact quality scoring algorithm that evaluates
relationships based on multiple dimensions including interaction frequency, recency,
meeting patterns, response reliability, and more.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field, validator
import statistics
import re
from collections import defaultdict, Counter

# Configure logging
logger = logging.getLogger(__name__)


class ScoringWeights(BaseModel):
    """Configurable weights for different scoring components"""
    
    frequency_weight: float = Field(0.25, ge=0.0, le=1.0, description="Weight for interaction frequency")
    recency_weight: float = Field(0.15, ge=0.0, le=1.0, description="Weight for interaction recency")
    meeting_consistency_weight: float = Field(0.15, ge=0.0, le=1.0, description="Weight for meeting consistency")
    response_reliability_weight: float = Field(0.15, ge=0.0, le=1.0, description="Weight for response reliability")
    communication_quality_weight: float = Field(0.10, ge=0.0, le=1.0, description="Weight for communication quality")
    sentiment_weight: float = Field(0.10, ge=0.0, le=1.0, description="Weight for sentiment analysis")
    professional_context_weight: float = Field(0.05, ge=0.0, le=1.0, description="Weight for professional context")
    relationship_trajectory_weight: float = Field(0.05, ge=0.0, le=1.0, description="Weight for relationship trajectory")
    
    @validator('*', pre=True)
    def validate_weights_sum(cls, v, values):
        """Ensure all weights sum to 1.0"""
        if len(values) == 7:  # All weights have been set
            total = sum(values.values()) + v
            if abs(total - 1.0) > 0.001:
                raise ValueError(f"All weights must sum to 1.0, got {total}")
        return v


@dataclass
class ContactMetrics:
    """Metrics calculated for a contact"""
    total_interactions: int
    email_count: int
    meeting_count: int
    call_count: int
    days_since_last_interaction: int
    interaction_frequency_per_month: float
    response_rate: float
    avg_response_time_hours: float
    meeting_attendance_rate: float
    communication_depth_score: float
    sentiment_score: float
    professional_relevance_score: float
    relationship_growth_rate: float
    consistency_score: float
    engagement_quality_score: float
    mutual_interaction_ratio: float
    contact_initiated_ratio: float


class ContactScoringService:
    """Service for scoring contact relationship quality"""
    
    def __init__(self):
        self.default_weights = ScoringWeights()
        self.tier_thresholds = {
            "inner_circle": 0.8,
            "strong_network": 0.6,
            "active_network": 0.4,
            "peripheral": 0.2,
            "dormant": 0.0
        }
        self.tier_descriptions = {
            "inner_circle": "Your closest professional relationships with frequent, high-quality interactions",
            "strong_network": "Important contacts with regular communication and strong professional ties",
            "active_network": "Active professional relationships with moderate interaction frequency",
            "peripheral": "Occasional contacts with limited but meaningful interactions",
            "dormant": "Inactive relationships that may need attention or re-engagement"
        }
    
    def get_default_weights(self) -> Dict[str, float]:
        """Get default scoring weights"""
        return self.default_weights.model_dump()
    
    def get_contact_tiers(self) -> Dict[str, str]:
        """Get contact tier descriptions"""
        return self.tier_descriptions
    
    async def score_contact(
        self,
        contact_data: Dict[str, Any],
        interactions: List[Dict[str, Any]],
        custom_weights: Optional[ScoringWeights] = None
    ) -> Dict[str, Any]:
        """
        Score a single contact based on interaction history
        
        Args:
            contact_data: Contact information
            interactions: List of interactions with the contact
            custom_weights: Optional custom scoring weights
            
        Returns:
            Comprehensive scoring result
        """
        
        weights = custom_weights or self.default_weights
        
        # Calculate metrics
        metrics = self._calculate_contact_metrics(contact_data, interactions)
        
        # Calculate component scores
        component_scores = self._calculate_component_scores(metrics, interactions)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(component_scores, weights)
        
        # Determine tier
        tier = self._determine_tier(overall_score)
        
        # Generate insights and recommendations
        insights = self._generate_insights(metrics, component_scores, interactions)
        recommendations = self._generate_recommendations(metrics, component_scores, tier)
        
        # Calculate confidence level
        confidence_level = self._calculate_confidence_level(metrics, interactions)
        
        return {
            "contact_id": contact_data.get("id", "unknown"),
            "overall_score": round(overall_score, 3),
            "tier": tier,
            "tier_description": self.tier_descriptions[tier],
            "component_scores": {
                "frequency_score": round(component_scores["frequency"], 3),
                "recency_score": round(component_scores["recency"], 3),
                "meeting_consistency_score": round(component_scores["meeting_consistency"], 3),
                "response_reliability_score": round(component_scores["response_reliability"], 3),
                "communication_quality_score": round(component_scores["communication_quality"], 3),
                "sentiment_score": round(component_scores["sentiment"], 3),
                "professional_context_score": round(component_scores["professional_context"], 3),
                "trajectory_score": round(component_scores["trajectory"], 3)
            },
            "metrics": {
                "total_interactions": metrics.total_interactions,
                "days_since_last_interaction": metrics.days_since_last_interaction,
                "interaction_frequency_per_month": round(metrics.interaction_frequency_per_month, 2),
                "response_rate": round(metrics.response_rate, 3),
                "meeting_attendance_rate": round(metrics.meeting_attendance_rate, 3),
                "communication_depth_score": round(metrics.communication_depth_score, 3),
                "sentiment_score": round(metrics.sentiment_score, 3),
                "professional_relevance_score": round(metrics.professional_relevance_score, 3),
                "relationship_growth_rate": round(metrics.relationship_growth_rate, 3),
                "consistency_score": round(metrics.consistency_score, 3),
                "engagement_quality_score": round(metrics.engagement_quality_score, 3),
                "mutual_interaction_ratio": round(metrics.mutual_interaction_ratio, 3),
                "contact_initiated_ratio": round(metrics.contact_initiated_ratio, 3)
            },
            "insights": insights,
            "recommendations": recommendations,
            "confidence_level": round(confidence_level, 3),
            "score_interpretation": self._get_score_interpretation(overall_score, tier),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    async def score_contacts_batch(
        self,
        contacts_data: List[Dict[str, Any]],
        custom_weights: Optional[ScoringWeights] = None
    ) -> List[Dict[str, Any]]:
        """
        Score multiple contacts in batch
        
        Args:
            contacts_data: List of contact data with interactions
            custom_weights: Optional custom scoring weights
            
        Returns:
            List of scoring results
        """
        
        results = []
        
        for contact_item in contacts_data:
            contact_data = contact_item["contact_data"]
            interactions = contact_item["interactions"]
            
            try:
                result = await self.score_contact(contact_data, interactions, custom_weights)
                results.append(result)
            except Exception as e:
                logger.error(f"Error scoring contact {contact_data.get('id', 'unknown')}: {e}")
                # Continue with other contacts
                continue
        
        return results
    
    def _calculate_contact_metrics(
        self,
        contact_data: Dict[str, Any],
        interactions: List[Dict[str, Any]]
    ) -> ContactMetrics:
        """Calculate comprehensive metrics for a contact"""
        
        if not interactions:
            return ContactMetrics(
                total_interactions=0,
                email_count=0,
                meeting_count=0,
                call_count=0,
                days_since_last_interaction=999,
                interaction_frequency_per_month=0.0,
                response_rate=0.0,
                avg_response_time_hours=0.0,
                meeting_attendance_rate=0.0,
                communication_depth_score=0.0,
                sentiment_score=0.5,
                professional_relevance_score=0.0,
                relationship_growth_rate=0.0,
                consistency_score=0.0,
                engagement_quality_score=0.0,
                mutual_interaction_ratio=0.0,
                contact_initiated_ratio=0.0
            )
        
        # Basic counts
        total_interactions = len(interactions)
        email_count = sum(1 for i in interactions if i.get("interaction_type") == "email")
        meeting_count = sum(1 for i in interactions if i.get("interaction_type") == "meeting")
        call_count = sum(1 for i in interactions if i.get("interaction_type") == "call")
        
        # Sort interactions by date
        sorted_interactions = sorted(
            interactions,
            key=lambda x: x.get("interaction_date", datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True
        )
        
        # Days since last interaction
        last_interaction_date = sorted_interactions[0].get("interaction_date")
        if isinstance(last_interaction_date, str):
            last_interaction_date = datetime.fromisoformat(last_interaction_date.replace('Z', '+00:00'))
        
        days_since_last = (datetime.now(timezone.utc) - last_interaction_date).days
        
        # Interaction frequency (per month)
        first_interaction_date = sorted_interactions[-1].get("interaction_date")
        if isinstance(first_interaction_date, str):
            first_interaction_date = datetime.fromisoformat(first_interaction_date.replace('Z', '+00:00'))
        
        total_days = (last_interaction_date - first_interaction_date).days + 1
        frequency_per_month = (total_interactions / max(total_days, 1)) * 30
        
        # Response rate calculation
        response_rate = self._calculate_response_rate(interactions)
        
        # Average response time
        avg_response_time = self._calculate_avg_response_time(interactions)
        
        # Meeting attendance rate
        meeting_attendance_rate = self._calculate_meeting_attendance_rate(interactions)
        
        # Communication depth score
        communication_depth_score = self._calculate_communication_depth(interactions)
        
        # Sentiment score
        sentiment_score = self._calculate_sentiment_score(interactions)
        
        # Professional relevance score
        professional_relevance_score = self._calculate_professional_relevance(contact_data, interactions)
        
        # Relationship growth rate
        relationship_growth_rate = self._calculate_relationship_growth_rate(interactions)
        
        # Consistency score
        consistency_score = self._calculate_consistency_score(interactions)
        
        # Engagement quality score
        engagement_quality_score = self._calculate_engagement_quality(interactions)
        
        # Interaction direction ratios
        mutual_ratio, contact_initiated_ratio = self._calculate_interaction_ratios(interactions)
        
        return ContactMetrics(
            total_interactions=total_interactions,
            email_count=email_count,
            meeting_count=meeting_count,
            call_count=call_count,
            days_since_last_interaction=days_since_last,
            interaction_frequency_per_month=frequency_per_month,
            response_rate=response_rate,
            avg_response_time_hours=avg_response_time,
            meeting_attendance_rate=meeting_attendance_rate,
            communication_depth_score=communication_depth_score,
            sentiment_score=sentiment_score,
            professional_relevance_score=professional_relevance_score,
            relationship_growth_rate=relationship_growth_rate,
            consistency_score=consistency_score,
            engagement_quality_score=engagement_quality_score,
            mutual_interaction_ratio=mutual_ratio,
            contact_initiated_ratio=contact_initiated_ratio
        )
    
    def _calculate_response_rate(self, interactions: List[Dict[str, Any]]) -> float:
        """Calculate response rate based on email exchanges"""
        
        email_interactions = [i for i in interactions if i.get("interaction_type") == "email"]
        if len(email_interactions) < 2:
            return 0.5  # Neutral score for insufficient data
        
        # Sort by date
        email_interactions.sort(key=lambda x: x.get("interaction_date", datetime.min.replace(tzinfo=timezone.utc)))
        
        responses = 0
        outbound_emails = 0
        
        for i, interaction in enumerate(email_interactions):
            if interaction.get("direction") == "outbound":
                outbound_emails += 1
                # Check if there's a response within 7 days
                if i + 1 < len(email_interactions):
                    next_interaction = email_interactions[i + 1]
                    if next_interaction.get("direction") == "inbound":
                        time_diff = (next_interaction.get("interaction_date") - interaction.get("interaction_date")).days
                        if time_diff <= 7:
                            responses += 1
        
        return responses / max(outbound_emails, 1)
    
    def _calculate_avg_response_time(self, interactions: List[Dict[str, Any]]) -> float:
        """Calculate average response time in hours"""
        
        email_interactions = [i for i in interactions if i.get("interaction_type") == "email"]
        if len(email_interactions) < 2:
            return 24.0  # Default 24 hours
        
        email_interactions.sort(key=lambda x: x.get("interaction_date", datetime.min.replace(tzinfo=timezone.utc)))
        
        response_times = []
        
        for i, interaction in enumerate(email_interactions):
            if interaction.get("direction") == "outbound" and i + 1 < len(email_interactions):
                next_interaction = email_interactions[i + 1]
                if next_interaction.get("direction") == "inbound":
                    time_diff = (next_interaction.get("interaction_date") - interaction.get("interaction_date")).total_seconds() / 3600
                    if time_diff <= 168:  # Within a week
                        response_times.append(time_diff)
        
        return statistics.mean(response_times) if response_times else 24.0
    
    def _calculate_meeting_attendance_rate(self, interactions: List[Dict[str, Any]]) -> float:
        """Calculate meeting attendance rate"""
        
        meetings = [i for i in interactions if i.get("interaction_type") == "meeting"]
        if not meetings:
            return 0.5  # Neutral score for no meetings
        
        # Assume all logged meetings were attended (in real implementation, check for cancellations)
        return 1.0
    
    def _calculate_communication_depth(self, interactions: List[Dict[str, Any]]) -> float:
        """Calculate communication depth based on content length and complexity"""
        
        if not interactions:
            return 0.0
        
        depth_scores = []
        
        for interaction in interactions:
            content = interaction.get("content", "")
            if not content:
                depth_scores.append(0.1)
                continue
            
            # Basic depth indicators
            word_count = len(content.split())
            has_questions = "?" in content
            has_detailed_info = any(keyword in content.lower() for keyword in [
                "project", "meeting", "discussion", "proposal", "plan", "strategy"
            ])
            
            # Calculate depth score
            depth = min(word_count / 100, 1.0)  # Normalize by word count
            if has_questions:
                depth += 0.2
            if has_detailed_info:
                depth += 0.3
            
            depth_scores.append(min(depth, 1.0))
        
        return statistics.mean(depth_scores)
    
    def _calculate_sentiment_score(self, interactions: List[Dict[str, Any]]) -> float:
        """Calculate sentiment score based on content analysis"""
        
        if not interactions:
            return 0.5  # Neutral
        
        positive_keywords = [
            "thanks", "great", "excellent", "wonderful", "appreciate", "love",
            "fantastic", "amazing", "perfect", "brilliant", "outstanding"
        ]
        
        negative_keywords = [
            "sorry", "unfortunately", "problem", "issue", "concern", "worried",
            "disappointed", "frustrated", "difficult", "challenging"
        ]
        
        sentiment_scores = []
        
        for interaction in interactions:
            content = interaction.get("content", "").lower()
            if not content:
                sentiment_scores.append(0.5)
                continue
            
            positive_count = sum(1 for keyword in positive_keywords if keyword in content)
            negative_count = sum(1 for keyword in negative_keywords if keyword in content)
            
            # Calculate sentiment (0.0 = very negative, 0.5 = neutral, 1.0 = very positive)
            if positive_count + negative_count == 0:
                sentiment = 0.5
            else:
                sentiment = (positive_count + 0.5 * (len(content.split()) - positive_count - negative_count)) / len(content.split())
                sentiment = max(0.0, min(1.0, sentiment))
            
            sentiment_scores.append(sentiment)
        
        return statistics.mean(sentiment_scores)
    
    def _calculate_professional_relevance(self, contact_data: Dict[str, Any], interactions: List[Dict[str, Any]]) -> float:
        """Calculate professional relevance score"""
        
        relevance_score = 0.0
        
        # Company and job title relevance
        company = contact_data.get("company", "").lower()
        job_title = contact_data.get("job_title", "").lower()
        
        # Professional indicators
        professional_companies = ["inc", "corp", "llc", "ltd", "company", "technologies", "solutions"]
        professional_titles = ["manager", "director", "vp", "ceo", "cto", "engineer", "analyst", "consultant"]
        
        if any(indicator in company for indicator in professional_companies):
            relevance_score += 0.3
        
        if any(title in job_title for title in professional_titles):
            relevance_score += 0.3
        
        # Meeting-based interactions indicate professional relationship
        meeting_ratio = len([i for i in interactions if i.get("interaction_type") == "meeting"]) / max(len(interactions), 1)
        relevance_score += meeting_ratio * 0.4
        
        return min(relevance_score, 1.0)
    
    def _calculate_relationship_growth_rate(self, interactions: List[Dict[str, Any]]) -> float:
        """Calculate relationship growth rate over time"""
        
        if len(interactions) < 3:
            return 0.5  # Neutral for insufficient data
        
        # Sort interactions by date
        sorted_interactions = sorted(
            interactions,
            key=lambda x: x.get("interaction_date", datetime.min.replace(tzinfo=timezone.utc))
        )
        
        # Split into first half and second half
        mid_point = len(sorted_interactions) // 2
        first_half = sorted_interactions[:mid_point]
        second_half = sorted_interactions[mid_point:]
        
        # Calculate interaction frequency for each half
        first_half_days = (first_half[-1].get("interaction_date") - first_half[0].get("interaction_date")).days + 1
        second_half_days = (second_half[-1].get("interaction_date") - second_half[0].get("interaction_date")).days + 1
        
        first_half_frequency = len(first_half) / max(first_half_days, 1)
        second_half_frequency = len(second_half) / max(second_half_days, 1)
        
        # Calculate growth rate
        if first_half_frequency == 0:
            return 1.0 if second_half_frequency > 0 else 0.5
        
        growth_rate = (second_half_frequency - first_half_frequency) / first_half_frequency
        
        # Normalize to 0-1 scale
        return max(0.0, min(1.0, (growth_rate + 1) / 2))
    
    def _calculate_consistency_score(self, interactions: List[Dict[str, Any]]) -> float:
        """Calculate consistency of interactions over time"""
        
        if len(interactions) < 3:
            return 0.5
        
        # Sort interactions by date
        sorted_interactions = sorted(
            interactions,
            key=lambda x: x.get("interaction_date", datetime.min.replace(tzinfo=timezone.utc))
        )
        
        # Calculate gaps between interactions
        gaps = []
        for i in range(1, len(sorted_interactions)):
            gap = (sorted_interactions[i].get("interaction_date") - sorted_interactions[i-1].get("interaction_date")).days
            gaps.append(gap)
        
        if not gaps:
            return 0.5
        
        # Calculate coefficient of variation (lower = more consistent)
        mean_gap = statistics.mean(gaps)
        if mean_gap == 0:
            return 1.0
        
        std_gap = statistics.stdev(gaps) if len(gaps) > 1 else 0
        cv = std_gap / mean_gap
        
        # Convert to consistency score (0 = inconsistent, 1 = very consistent)
        consistency = max(0.0, 1.0 - min(cv, 1.0))
        
        return consistency
    
    def _calculate_engagement_quality(self, interactions: List[Dict[str, Any]]) -> float:
        """Calculate overall engagement quality"""
        
        if not interactions:
            return 0.0
        
        quality_indicators = []
        
        for interaction in interactions:
            quality = 0.0
            
            # Duration for meetings/calls
            if interaction.get("interaction_type") in ["meeting", "call"]:
                duration = interaction.get("duration_minutes", 0)
                if duration > 0:
                    quality += min(duration / 60, 1.0) * 0.5  # Normalize by hour
            
            # Content quality for emails
            content = interaction.get("content", "")
            if content:
                word_count = len(content.split())
                quality += min(word_count / 50, 1.0) * 0.3  # Normalize by 50 words
                
                # Check for engagement indicators
                if any(indicator in content.lower() for indicator in ["question", "?", "thoughts", "opinion"]):
                    quality += 0.2
            
            # Interaction type quality
            type_quality = {
                "meeting": 1.0,
                "call": 0.8,
                "email": 0.6,
                "message": 0.4
            }
            quality += type_quality.get(interaction.get("interaction_type", ""), 0.3)
            
            quality_indicators.append(min(quality, 1.0))
        
        return statistics.mean(quality_indicators)
    
    def _calculate_interaction_ratios(self, interactions: List[Dict[str, Any]]) -> Tuple[float, float]:
        """Calculate mutual interaction ratio and contact-initiated ratio"""
        
        if not interactions:
            return 0.0, 0.0
        
        mutual_count = sum(1 for i in interactions if i.get("direction") == "mutual")
        inbound_count = sum(1 for i in interactions if i.get("direction") == "inbound")
        outbound_count = sum(1 for i in interactions if i.get("direction") == "outbound")
        
        total = len(interactions)
        mutual_ratio = mutual_count / total
        contact_initiated_ratio = inbound_count / total
        
        return mutual_ratio, contact_initiated_ratio
    
    def _calculate_component_scores(
        self,
        metrics: ContactMetrics,
        interactions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate individual component scores"""
        
        # Frequency score (based on interaction frequency)
        frequency_score = min(metrics.interaction_frequency_per_month / 10, 1.0)  # Normalize by 10 interactions/month
        
        # Recency score (based on days since last interaction)
        recency_score = max(0.0, 1.0 - (metrics.days_since_last_interaction / 90))  # 90 days = 0 score
        
        # Meeting consistency score
        meeting_consistency_score = metrics.meeting_attendance_rate * (metrics.meeting_count / max(metrics.total_interactions, 1))
        
        # Response reliability score
        response_reliability_score = (metrics.response_rate + (1.0 - min(metrics.avg_response_time_hours / 48, 1.0))) / 2
        
        # Communication quality score
        communication_quality_score = (metrics.communication_depth_score + metrics.engagement_quality_score) / 2
        
        # Sentiment score (already calculated)
        sentiment_score = metrics.sentiment_score
        
        # Professional context score
        professional_context_score = metrics.professional_relevance_score
        
        # Relationship trajectory score
        trajectory_score = (metrics.relationship_growth_rate + metrics.consistency_score) / 2
        
        return {
            "frequency": frequency_score,
            "recency": recency_score,
            "meeting_consistency": meeting_consistency_score,
            "response_reliability": response_reliability_score,
            "communication_quality": communication_quality_score,
            "sentiment": sentiment_score,
            "professional_context": professional_context_score,
            "trajectory": trajectory_score
        }
    
    def _calculate_overall_score(
        self,
        component_scores: Dict[str, float],
        weights: ScoringWeights
    ) -> float:
        """Calculate weighted overall score"""
        
        overall_score = (
            component_scores["frequency"] * weights.frequency_weight +
            component_scores["recency"] * weights.recency_weight +
            component_scores["meeting_consistency"] * weights.meeting_consistency_weight +
            component_scores["response_reliability"] * weights.response_reliability_weight +
            component_scores["communication_quality"] * weights.communication_quality_weight +
            component_scores["sentiment"] * weights.sentiment_weight +
            component_scores["professional_context"] * weights.professional_context_weight +
            component_scores["trajectory"] * weights.relationship_trajectory_weight
        )
        
        return max(0.0, min(1.0, overall_score))
    
    def _determine_tier(self, overall_score: float) -> str:
        """Determine contact tier based on overall score"""
        
        for tier, threshold in self.tier_thresholds.items():
            if overall_score >= threshold:
                return tier
        
        return "dormant"
    
    def _calculate_confidence_level(self, metrics: ContactMetrics, interactions: List[Dict[str, Any]]) -> float:
        """Calculate confidence level in the scoring"""
        
        confidence_factors = []
        
        # Data volume confidence
        interaction_confidence = min(metrics.total_interactions / 10, 1.0)  # 10+ interactions = full confidence
        confidence_factors.append(interaction_confidence)
        
        # Time span confidence
        if interactions:
            sorted_interactions = sorted(
                interactions,
                key=lambda x: x.get("interaction_date", datetime.min.replace(tzinfo=timezone.utc))
            )
            time_span_days = (sorted_interactions[-1].get("interaction_date") - sorted_interactions[0].get("interaction_date")).days
            time_confidence = min(time_span_days / 180, 1.0)  # 6 months = full confidence
            confidence_factors.append(time_confidence)
        else:
            confidence_factors.append(0.0)
        
        # Interaction diversity confidence
        interaction_types = set(i.get("interaction_type") for i in interactions)
        diversity_confidence = min(len(interaction_types) / 3, 1.0)  # 3+ types = full confidence
        confidence_factors.append(diversity_confidence)
        
        return statistics.mean(confidence_factors)
    
    def _generate_insights(
        self,
        metrics: ContactMetrics,
        component_scores: Dict[str, float],
        interactions: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate AI-powered insights about the relationship"""
        
        insights = []
        
        # Frequency insights
        if component_scores["frequency"] > 0.8:
            insights.append("Very active relationship with frequent interactions")
        elif component_scores["frequency"] < 0.3:
            insights.append("Low interaction frequency - relationship may need more attention")
        
        # Recency insights
        if metrics.days_since_last_interaction > 60:
            insights.append(f"No recent contact for {metrics.days_since_last_interaction} days - consider reaching out")
        elif metrics.days_since_last_interaction < 7:
            insights.append("Recent active communication indicates strong engagement")
        
        # Response reliability insights
        if metrics.response_rate > 0.8:
            insights.append("Highly responsive contact - reliable for important communications")
        elif metrics.response_rate < 0.3:
            insights.append("Low response rate - may prefer alternative communication methods")
        
        # Professional context insights
        if metrics.professional_relevance_score > 0.7:
            insights.append("Strong professional relationship with business relevance")
        
        # Sentiment insights
        if metrics.sentiment_score > 0.7:
            insights.append("Positive communication tone indicates good relationship health")
        elif metrics.sentiment_score < 0.4:
            insights.append("Communication tone suggests potential relationship challenges")
        
        # Growth insights
        if metrics.relationship_growth_rate > 0.7:
            insights.append("Relationship is strengthening over time")
        elif metrics.relationship_growth_rate < 0.3:
            insights.append("Relationship activity has declined - may need re-engagement")
        
        return insights[:5]  # Limit to top 5 insights
    
    def _generate_recommendations(
        self,
        metrics: ContactMetrics,
        component_scores: Dict[str, float],
        tier: str
    ) -> List[str]:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        # Tier-based recommendations
        if tier == "dormant":
            recommendations.append("Schedule a catch-up call or send a re-engagement email")
            recommendations.append("Share relevant industry news or insights to restart conversation")
        elif tier == "peripheral":
            recommendations.append("Increase interaction frequency with regular check-ins")
            recommendations.append("Invite to relevant events or meetings")
        elif tier == "active_network":
            recommendations.append("Maintain current engagement level with periodic updates")
            recommendations.append("Look for collaboration opportunities")
        elif tier == "strong_network":
            recommendations.append("Leverage this relationship for strategic initiatives")
            recommendations.append("Consider introducing them to other valuable contacts")
        elif tier == "inner_circle":
            recommendations.append("Continue nurturing this key relationship")
            recommendations.append("Seek their input on important decisions")
        
        # Specific metric-based recommendations
        if metrics.response_rate < 0.5:
            recommendations.append("Try different communication channels (phone vs email)")
        
        if metrics.meeting_count == 0 and metrics.total_interactions > 5:
            recommendations.append("Suggest a face-to-face or video meeting to deepen the relationship")
        
        if component_scores["sentiment"] < 0.5:
            recommendations.append("Address any potential concerns or misunderstandings")
        
        if metrics.days_since_last_interaction > 30:
            recommendations.append("Send a personalized message to re-establish contact")
        
        return recommendations[:4]  # Limit to top 4 recommendations
    
    def _get_score_interpretation(self, overall_score: float, tier: str) -> str:
        """Get human-readable score interpretation"""
        
        if overall_score >= 0.8:
            return f"Excellent relationship quality ({tier}). This is a key professional contact with strong, consistent engagement."
        elif overall_score >= 0.6:
            return f"Good relationship quality ({tier}). Regular interaction with positive engagement patterns."
        elif overall_score >= 0.4:
            return f"Moderate relationship quality ({tier}). Some engagement but room for improvement."
        elif overall_score >= 0.2:
            return f"Limited relationship quality ({tier}). Minimal interaction - consider re-engagement strategies."
        else:
            return f"Inactive relationship ({tier}). No recent meaningful interaction - may need significant re-engagement effort." 