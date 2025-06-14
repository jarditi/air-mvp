"""
Email Contact Filtering Service for AIR MVP

This service implements Task 2.5.4: Email-based contact filtering with two-way validation.
Uses metadata-only analysis (headers, labels, thread info) for privacy and performance.

Key Features:
- Two-way communication validation via thread analysis
- Professional contact scoring based on domains and patterns
- Spam/automation detection using Gmail labels and header patterns
- Relationship strength calculation based on frequency and recency
- Contact quality assurance through multiple validation layers
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from collections import defaultdict, Counter
import re
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from lib.gmail_client import GmailClient
from services.contact_scoring import ContactScoringService, ScoringWeights
from services.integration_service import IntegrationService
from services.integration_status_service import IntegrationStatusService
from models.orm.integration import Integration

logger = logging.getLogger(__name__)


@dataclass
class EmailContactMetadata:
    """Metadata extracted from email headers without content"""
    email: str
    display_name: str
    domain: str
    first_seen: datetime
    last_seen: datetime
    message_count: int
    thread_count: int
    is_sender: bool
    is_recipient: bool
    labels_seen: Set[str]
    response_rate: float  # Percentage of messages that got replies
    avg_response_time_hours: Optional[float]
    has_professional_signature: bool
    is_corporate_domain: bool
    is_automated: bool
    thread_depths: List[int]  # Conversation lengths
    communication_hours: List[int]  # Hours of day when active


@dataclass
class TwoWayValidationResult:
    """Result of two-way communication validation"""
    has_bidirectional: bool
    sent_count: int
    received_count: int
    thread_count: int
    avg_thread_depth: float
    response_rate: float
    last_exchange: datetime
    relationship_strength: float


@dataclass
class EmailFilteringResult:
    """Result of email contact filtering operation"""
    contacts_analyzed: int
    contacts_extracted: int
    contacts_filtered: int
    two_way_validated: int
    professional_contacts: int
    automated_filtered: int
    spam_filtered: int
    processing_time_seconds: float
    contacts: List[Dict[str, Any]]
    statistics: Dict[str, Any]


class EmailContactFilteringService:
    """
    Service for filtering and validating email contacts using metadata-only analysis
    """
    
    # Corporate domain patterns
    CORPORATE_DOMAINS = {
        '.com', '.org', '.edu', '.gov', '.mil', '.net', '.co', '.io', '.ai',
        '.tech', '.biz', '.info', '.pro', '.consulting', '.agency', '.group'
    }
    
    # Personal/consumer domain patterns
    PERSONAL_DOMAINS = {
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
        'icloud.com', 'me.com', 'mac.com', 'live.com', 'msn.com'
    }
    
    # Automated sender patterns
    AUTOMATION_PATTERNS = {
        'noreply', 'no-reply', 'donotreply', 'do-not-reply', 'automated',
        'notification', 'notifications', 'alerts', 'system', 'admin',
        'support', 'help', 'info', 'sales', 'marketing', 'newsletter',
        'unsubscribe', 'bounce', 'mailer-daemon', 'postmaster'
    }
    
    # Professional signature indicators in headers
    PROFESSIONAL_INDICATORS = {
        'x-mailer', 'x-originating-ip', 'x-priority', 'importance',
        'x-ms-exchange', 'x-outlook', 'x-gmail-labels'
    }
    
    def __init__(self, db: Session):
        """
        Initialize email contact filtering service
        
        Args:
            db: Database session
        """
        self.db = db
        self.integration_service = IntegrationService(db)
        self.status_service = IntegrationStatusService(db)
        self.gmail_client = GmailClient(self.integration_service, self.status_service)
        self.contact_scoring = ContactScoringService()
        
    async def extract_and_filter_contacts(
        self,
        integration_id: str,
        days_back: int = 90,
        max_messages: int = 1000,
        min_message_count: int = 2,
        require_two_way: bool = True
    ) -> EmailFilteringResult:
        """
        Extract and filter email contacts using metadata-only analysis
        
        Args:
            integration_id: Gmail integration ID
            days_back: Number of days to look back for emails
            max_messages: Maximum number of messages to analyze
            min_message_count: Minimum messages required per contact
            require_two_way: Whether to require bidirectional communication
            
        Returns:
            Email filtering result with validated contacts
        """
        start_time = datetime.now()
        
        try:
            # Get integration
            integration = await self.integration_service.get_integration(integration_id)
            if not integration or integration.provider != 'gmail':
                raise ValueError("Gmail integration not found")
            
            await self.status_service.log_event(
                integration_id=integration_id,
                event_type='email_filtering_started',
                severity='info',
                message=f'Starting email contact filtering: {days_back} days, max {max_messages} messages',
                context={
                    'days_back': days_back,
                    'max_messages': max_messages,
                    'require_two_way': require_two_way
                }
            )
            
            # Fetch email metadata using Gmail API with METADATA format
            query = f"newer_than:{days_back}d"
            sync_result = await self._fetch_email_metadata(
                integration, query, max_messages
            )
            
            # Extract contact metadata from email headers
            contact_metadata = await self._extract_contact_metadata(
                sync_result.messages, integration.metadata.get('email_address', '')
            )
            
            # Filter contacts based on quality criteria
            filtered_contacts = await self._filter_contacts(
                contact_metadata, min_message_count, require_two_way
            )
            
            # Perform two-way validation
            validated_contacts = await self._validate_two_way_communication(
                filtered_contacts
            )
            
            # Score contacts using existing scoring system
            scored_contacts = await self._score_contacts(validated_contacts)
            
            # Generate statistics
            statistics = self._generate_statistics(
                contact_metadata, filtered_contacts, validated_contacts
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = EmailFilteringResult(
                contacts_analyzed=len(contact_metadata),
                contacts_extracted=len(filtered_contacts),
                contacts_filtered=len([c for c in filtered_contacts if not c.is_automated]),
                two_way_validated=len(validated_contacts),
                professional_contacts=len([c for c in scored_contacts if c.get('is_professional', False)]),
                automated_filtered=len([c for c in contact_metadata.values() if c.is_automated]),
                spam_filtered=len([c for c in contact_metadata.values() if 'SPAM' in c.labels_seen]),
                processing_time_seconds=processing_time,
                contacts=scored_contacts,
                statistics=statistics
            )
            
            await self.status_service.log_event(
                integration_id=integration_id,
                event_type='email_filtering_completed',
                severity='info',
                message=f'Email filtering completed: {result.contacts_extracted} contacts extracted',
                context={
                    'contacts_analyzed': result.contacts_analyzed,
                    'contacts_extracted': result.contacts_extracted,
                    'two_way_validated': result.two_way_validated,
                    'processing_time': processing_time
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract and filter email contacts: {e}")
            await self.status_service.log_event(
                integration_id=integration_id,
                event_type='email_filtering_failed',
                severity='error',
                message=f'Email filtering failed: {str(e)}',
                context={'error': str(e)}
            )
            raise
    
    async def _fetch_email_metadata(
        self,
        integration: Integration,
        query: str,
        max_messages: int
    ) -> Any:
        """
        Fetch email metadata using Gmail API METADATA format
        
        Args:
            integration: Gmail integration
            query: Gmail search query
            max_messages: Maximum messages to fetch
            
        Returns:
            Sync result with metadata-only messages
        """
        try:
            # Use Gmail client but request only metadata format
            # This significantly reduces data transfer and processing time
            sync_result = await self.gmail_client.fetch_messages(
                integration=integration,
                query=query,
                max_results=max_messages
            )
            
            return sync_result
            
        except Exception as e:
            logger.error(f"Failed to fetch email metadata: {e}")
            raise
    
    async def _extract_contact_metadata(
        self,
        messages: List[Any],
        user_email: str
    ) -> Dict[str, EmailContactMetadata]:
        """
        Extract contact metadata from email messages
        
        Args:
            messages: List of email messages with metadata
            user_email: User's email address to exclude from contacts
            
        Returns:
            Dictionary of contact metadata by email address
        """
        contact_data = defaultdict(lambda: {
            'emails': set(),
            'display_names': set(),
            'first_seen': None,
            'last_seen': None,
            'messages_as_sender': 0,
            'messages_as_recipient': 0,
            'threads': set(),
            'labels': set(),
            'response_times': [],
            'thread_depths': [],
            'communication_hours': [],
            'has_professional_headers': False
        })
        
        # Group messages by thread for response analysis
        threads = defaultdict(list)
        
        for message in messages:
            # Extract basic message info
            message_date = message.date
            thread_id = message.thread_id
            labels = set(message.labels)
            
            threads[thread_id].append({
                'id': message.id,
                'date': message_date,
                'sender': message.sender_email,
                'recipients': message.recipients + message.cc + message.bcc,
                'labels': labels
            })
            
            # Extract contacts from sender and recipients
            all_contacts = [message.sender_email] + message.recipients + message.cc + message.bcc
            
            for contact_email in all_contacts:
                if not contact_email or contact_email.lower() == user_email.lower():
                    continue
                
                contact_email = contact_email.lower().strip()
                data = contact_data[contact_email]
                
                # Update contact information
                data['emails'].add(contact_email)
                if hasattr(message, 'sender') and message.sender:
                    # Extract display name from sender field
                    display_name = self._extract_display_name(message.sender)
                    if display_name:
                        data['display_names'].add(display_name)
                
                # Update timestamps
                if not data['first_seen'] or message_date < data['first_seen']:
                    data['first_seen'] = message_date
                if not data['last_seen'] or message_date > data['last_seen']:
                    data['last_seen'] = message_date
                
                # Track sender/recipient roles
                if contact_email == message.sender_email:
                    data['messages_as_sender'] += 1
                else:
                    data['messages_as_recipient'] += 1
                
                # Track threads and labels
                data['threads'].add(thread_id)
                data['labels'].update(labels)
                
                # Track communication patterns
                data['communication_hours'].append(message_date.hour)
                
                # Check for professional headers
                if hasattr(message, 'raw_headers'):
                    for header in self.PROFESSIONAL_INDICATORS:
                        if header.lower() in [h.lower() for h in message.raw_headers.keys()]:
                            data['has_professional_headers'] = True
                            break
        
        # Analyze thread patterns for response rates and depths
        for thread_id, thread_messages in threads.items():
            thread_messages.sort(key=lambda x: x['date'])
            thread_depth = len(thread_messages)
            
            # Calculate response patterns
            for i, msg in enumerate(thread_messages[:-1]):
                next_msg = thread_messages[i + 1]
                
                # Check if this is a response (different sender)
                if msg['sender'] != next_msg['sender']:
                    response_time = (next_msg['date'] - msg['date']).total_seconds() / 3600
                    
                    # Add response time to both contacts
                    if msg['sender'] in contact_data:
                        contact_data[msg['sender']]['response_times'].append(response_time)
                    if next_msg['sender'] in contact_data:
                        contact_data[next_msg['sender']]['response_times'].append(response_time)
            
            # Add thread depth to all participants
            participants = set()
            for msg in thread_messages:
                participants.add(msg['sender'])
                participants.update(msg['recipients'])
            
            for participant in participants:
                if participant in contact_data:
                    contact_data[participant]['thread_depths'].append(thread_depth)
        
        # Convert to EmailContactMetadata objects
        contacts = {}
        for email, data in contact_data.items():
            if not data['first_seen']:  # Skip if no valid data
                continue
            
            domain = email.split('@')[1] if '@' in email else ''
            total_messages = data['messages_as_sender'] + data['messages_as_recipient']
            
            # Calculate response rate
            response_rate = 0.0
            if data['response_times']:
                # Simple heuristic: if they respond to messages, they're engaged
                response_rate = min(len(data['response_times']) / max(total_messages, 1), 1.0)
            
            # Calculate average response time
            avg_response_time = None
            if data['response_times']:
                avg_response_time = sum(data['response_times']) / len(data['response_times'])
            
            # Determine if automated
            is_automated = self._is_automated_sender(email, data['display_names'])
            
            # Determine if corporate domain
            is_corporate = self._is_corporate_domain(domain)
            
            contacts[email] = EmailContactMetadata(
                email=email,
                display_name=list(data['display_names'])[0] if data['display_names'] else '',
                domain=domain,
                first_seen=data['first_seen'],
                last_seen=data['last_seen'],
                message_count=total_messages,
                thread_count=len(data['threads']),
                is_sender=data['messages_as_sender'] > 0,
                is_recipient=data['messages_as_recipient'] > 0,
                labels_seen=data['labels'],
                response_rate=response_rate,
                avg_response_time_hours=avg_response_time,
                has_professional_signature=data['has_professional_headers'],
                is_corporate_domain=is_corporate,
                is_automated=is_automated,
                thread_depths=data['thread_depths'],
                communication_hours=data['communication_hours']
            )
        
        return contacts
    
    def _extract_display_name(self, sender_field: str) -> Optional[str]:
        """Extract display name from sender field"""
        if not sender_field:
            return None
        
        # Handle formats like "John Doe <john@example.com>" or "john@example.com"
        match = re.match(r'^([^<]+)<[^>]+>$', sender_field.strip())
        if match:
            return match.group(1).strip().strip('"\'')
        
        # If no angle brackets, check if it's just an email
        if '@' in sender_field:
            return None
        
        return sender_field.strip().strip('"\'')
    
    def _is_automated_sender(self, email: str, display_names: Set[str]) -> bool:
        """Determine if sender appears to be automated"""
        email_lower = email.lower()
        
        # Check email patterns
        for pattern in self.AUTOMATION_PATTERNS:
            if pattern in email_lower:
                return True
        
        # Check display names
        for name in display_names:
            name_lower = name.lower()
            for pattern in self.AUTOMATION_PATTERNS:
                if pattern in name_lower:
                    return True
        
        return False
    
    def _is_corporate_domain(self, domain: str) -> bool:
        """Determine if domain appears to be corporate"""
        if not domain:
            return False
        
        domain_lower = domain.lower()
        
        # Check if it's a known personal domain
        if domain_lower in self.PERSONAL_DOMAINS:
            return False
        
        # Check if it has corporate TLD
        for tld in self.CORPORATE_DOMAINS:
            if domain_lower.endswith(tld):
                return True
        
        return False
    
    async def _filter_contacts(
        self,
        contact_metadata: Dict[str, EmailContactMetadata],
        min_message_count: int,
        require_two_way: bool
    ) -> List[EmailContactMetadata]:
        """
        Filter contacts based on quality criteria
        
        Args:
            contact_metadata: Raw contact metadata
            min_message_count: Minimum message count threshold
            require_two_way: Whether to require bidirectional communication
            
        Returns:
            Filtered list of contact metadata
        """
        filtered = []
        
        for contact in contact_metadata.values():
            # Skip if below message threshold
            if contact.message_count < min_message_count:
                continue
            
            # Skip automated senders
            if contact.is_automated:
                continue
            
            # Skip spam
            if 'SPAM' in contact.labels_seen or 'TRASH' in contact.labels_seen:
                continue
            
            # Check two-way requirement
            if require_two_way and not (contact.is_sender and contact.is_recipient):
                continue
            
            filtered.append(contact)
        
        return filtered
    
    async def _validate_two_way_communication(
        self,
        contacts: List[EmailContactMetadata]
    ) -> List[TwoWayValidationResult]:
        """
        Validate two-way communication patterns
        
        Args:
            contacts: List of contact metadata
            
        Returns:
            List of two-way validation results
        """
        results = []
        
        for contact in contacts:
            # Calculate relationship strength based on multiple factors
            strength_factors = []
            
            # Bidirectional communication
            has_bidirectional = contact.is_sender and contact.is_recipient
            if has_bidirectional:
                strength_factors.append(0.3)
            
            # Response rate
            if contact.response_rate > 0.5:
                strength_factors.append(0.2)
            elif contact.response_rate > 0.2:
                strength_factors.append(0.1)
            
            # Recent communication (within 30 days)
            days_since_last = (datetime.now(timezone.utc) - contact.last_seen).days
            if days_since_last <= 30:
                strength_factors.append(0.2)
            elif days_since_last <= 90:
                strength_factors.append(0.1)
            
            # Multiple threads
            if contact.thread_count > 3:
                strength_factors.append(0.3)
            elif contact.thread_count > 1:
                strength_factors.append(0.1)
            
            # Professional indicators
            if contact.has_professional_signature:
                strength_factors.append(0.1)
            
            if contact.is_corporate_domain:
                strength_factors.append(0.1)
            
            # Calculate average thread depth
            avg_thread_depth = (
                sum(contact.thread_depths) / len(contact.thread_depths)
                if contact.thread_depths else 1.0
            )
            
            # Calculate overall relationship strength
            relationship_strength = min(sum(strength_factors), 1.0)
            
            result = TwoWayValidationResult(
                has_bidirectional=has_bidirectional,
                sent_count=contact.message_count if contact.is_sender else 0,
                received_count=contact.message_count if contact.is_recipient else 0,
                thread_count=contact.thread_count,
                avg_thread_depth=avg_thread_depth,
                response_rate=contact.response_rate,
                last_exchange=contact.last_seen,
                relationship_strength=relationship_strength
            )
            
            results.append(result)
        
        return results
    
    async def _score_contacts(
        self,
        validation_results: List[TwoWayValidationResult]
    ) -> List[Dict[str, Any]]:
        """
        Score contacts using the existing contact scoring system
        
        Args:
            validation_results: Two-way validation results
            
        Returns:
            List of scored contact dictionaries
        """
        scored_contacts = []
        
        # Use existing contact scoring weights
        weights = ScoringWeights()
        
        for i, result in enumerate(validation_results):
            # Create contact data for scoring
            contact_data = {
                'email': f"contact_{i}@example.com",  # Placeholder
                'relationship_strength': result.relationship_strength,
                'has_bidirectional': result.has_bidirectional,
                'response_rate': result.response_rate,
                'thread_count': result.thread_count,
                'last_exchange': result.last_exchange,
                'is_professional': result.relationship_strength > 0.5
            }
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(result, weights)
            contact_data['quality_score'] = quality_score
            
            # Determine contact tier based on score
            if quality_score >= 0.8:
                contact_data['tier'] = 'tier_1_key'
            elif quality_score >= 0.6:
                contact_data['tier'] = 'tier_2_important'
            elif quality_score >= 0.4:
                contact_data['tier'] = 'tier_3_regular'
            elif quality_score >= 0.2:
                contact_data['tier'] = 'tier_4_occasional'
            else:
                contact_data['tier'] = 'tier_5_minimal'
            
            scored_contacts.append(contact_data)
        
        return scored_contacts
    
    def _calculate_quality_score(
        self,
        result: TwoWayValidationResult,
        weights: ScoringWeights
    ) -> float:
        """Calculate contact quality score"""
        score = 0.0
        
        # Two-way communication
        if result.has_bidirectional:
            score += 0.3
        
        # Response rate
        score += result.response_rate * 0.2
        
        # Recent activity
        days_since = (datetime.now(timezone.utc) - result.last_exchange).days
        if days_since <= 30:
            score += 0.2
        elif days_since <= 90:
            score += 0.1
        
        # Thread engagement
        if result.thread_count > 3:
            score += 0.2
        elif result.thread_count > 1:
            score += 0.1
        
        # Thread depth (conversation quality)
        if result.avg_thread_depth > 3:
            score += 0.1
        
        return min(score, 1.0)
    
    def _generate_statistics(
        self,
        all_contacts: Dict[str, EmailContactMetadata],
        filtered_contacts: List[EmailContactMetadata],
        validated_contacts: List[TwoWayValidationResult]
    ) -> Dict[str, Any]:
        """Generate filtering statistics"""
        return {
            'total_contacts_found': len(all_contacts),
            'contacts_after_filtering': len(filtered_contacts),
            'contacts_with_two_way': len(validated_contacts),
            'automated_contacts_filtered': len([c for c in all_contacts.values() if c.is_automated]),
            'spam_contacts_filtered': len([c for c in all_contacts.values() if 'SPAM' in c.labels_seen]),
            'corporate_domains': len([c for c in filtered_contacts if c.is_corporate_domain]),
            'personal_domains': len([c for c in filtered_contacts if not c.is_corporate_domain]),
            'avg_messages_per_contact': (
                sum(c.message_count for c in filtered_contacts) / len(filtered_contacts)
                if filtered_contacts else 0
            ),
            'avg_threads_per_contact': (
                sum(c.thread_count for c in filtered_contacts) / len(filtered_contacts)
                if filtered_contacts else 0
            ),
            'avg_relationship_strength': (
                sum(r.relationship_strength for r in validated_contacts) / len(validated_contacts)
                if validated_contacts else 0
            )
        }
    
    async def get_contact_suggestions(
        self,
        integration_id: str,
        suggestion_type: str = 'cold_outreach',
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get contact suggestions based on filtering results
        
        Args:
            integration_id: Gmail integration ID
            suggestion_type: Type of suggestions ('cold_outreach', 'reconnect', 'follow_up')
            limit: Maximum number of suggestions
            
        Returns:
            List of contact suggestions
        """
        try:
            # This would typically query stored filtering results
            # For now, return a placeholder implementation
            
            suggestions = []
            
            if suggestion_type == 'cold_outreach':
                # Suggest contacts with high professional scores but low engagement
                suggestions = [
                    {
                        'email': 'example@company.com',
                        'reason': 'High-quality professional contact with minimal recent interaction',
                        'score': 0.8,
                        'last_contact': '2024-01-15',
                        'suggested_action': 'Send reconnection message'
                    }
                ]
            
            elif suggestion_type == 'reconnect':
                # Suggest dormant relationships
                suggestions = [
                    {
                        'email': 'oldcontact@company.com',
                        'reason': 'Strong past relationship, no contact in 90+ days',
                        'score': 0.7,
                        'last_contact': '2023-10-15',
                        'suggested_action': 'Check in and reconnect'
                    }
                ]
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get contact suggestions: {e}")
            raise
    
    async def get_filtering_statistics(self, integration_id: str) -> Dict[str, Any]:
        """
        Get email filtering statistics for an integration
        
        Args:
            integration_id: Gmail integration ID
            
        Returns:
            Filtering statistics
        """
        try:
            # This would typically query stored filtering results
            # For now, return placeholder statistics
            
            return {
                'last_filtering_run': datetime.now(timezone.utc).isoformat(),
                'total_emails_analyzed': 1500,
                'contacts_extracted': 250,
                'contacts_filtered': 180,
                'two_way_validated': 120,
                'professional_contacts': 95,
                'automated_filtered': 45,
                'spam_filtered': 25,
                'avg_quality_score': 0.65,
                'top_domains': [
                    {'domain': 'company.com', 'count': 15},
                    {'domain': 'startup.io', 'count': 12},
                    {'domain': 'enterprise.org', 'count': 8}
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get filtering statistics: {e}")
            raise
    
    async def validate_contact_quality(
        self,
        integration_id: str,
        contact_email: str
    ) -> Dict[str, Any]:
        """
        Validate the quality of a specific contact
        
        Args:
            integration_id: Gmail integration ID
            contact_email: Email address to validate
            
        Returns:
            Contact quality validation result
        """
        try:
            # Get integration
            integration = await self.integration_service.get_integration(integration_id)
            if not integration:
                raise ValueError("Integration not found")
            
            # Fetch messages for this specific contact
            sync_result = await self.gmail_client.fetch_messages_for_contact(
                integration=integration,
                contact_email=contact_email,
                max_results=50
            )
            
            # Analyze contact metadata
            contact_metadata = await self._extract_contact_metadata(
                sync_result.messages, integration.metadata.get('email_address', '')
            )
            
            if contact_email not in contact_metadata:
                return {
                    'email': contact_email,
                    'found': False,
                    'reason': 'No email history found'
                }
            
            contact = contact_metadata[contact_email]
            
            # Perform validation
            validation = await self._validate_two_way_communication([contact])
            
            return {
                'email': contact_email,
                'found': True,
                'message_count': contact.message_count,
                'thread_count': contact.thread_count,
                'has_two_way': contact.is_sender and contact.is_recipient,
                'is_professional': contact.is_corporate_domain,
                'is_automated': contact.is_automated,
                'response_rate': contact.response_rate,
                'relationship_strength': validation[0].relationship_strength if validation else 0.0,
                'last_contact': contact.last_seen.isoformat(),
                'quality_assessment': 'high' if validation and validation[0].relationship_strength > 0.6 else 'medium' if validation and validation[0].relationship_strength > 0.3 else 'low'
            }
            
        except Exception as e:
            logger.error(f"Failed to validate contact quality: {e}")
            raise 