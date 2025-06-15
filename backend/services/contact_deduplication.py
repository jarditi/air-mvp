"""
Contact Deduplication Service (Task 2.5.5)

Advanced contact deduplication with fuzzy matching, multi-source support,
and intelligent confidence scoring for automated and manual merge workflows.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

try:
    from rapidfuzz import fuzz, process
except ImportError:
    # Fallback to fuzzywuzzy if rapidfuzz not available
    from fuzzywuzzy import fuzz, process

try:
    import phonenumbers
    from phonenumbers import NumberParseException
    PHONE_PARSING_AVAILABLE = True
except ImportError:
    PHONE_PARSING_AVAILABLE = False

from models.orm.contact import Contact
from models.orm.user import User

logger = logging.getLogger(__name__)


class MatchingStrategy(Enum):
    """Contact matching strategies with confidence levels"""
    EXACT_EMAIL = ("exact_email", 100)           # Perfect match
    EXACT_PHONE = ("exact_phone", 95)            # Very high confidence  
    EXACT_LINKEDIN = ("exact_linkedin", 90)      # High confidence
    FUZZY_NAME_COMPANY = ("fuzzy_name_company", 85)  # Good match with context
    FUZZY_NAME_EMAIL_DOMAIN = ("fuzzy_name_email_domain", 80)  # Name + email domain
    FUZZY_NAME_ONLY = ("fuzzy_name_only", 70)    # Name similarity only
    PARTIAL_EMAIL = ("partial_email", 60)        # Email alias/variation
    PARTIAL_MATCH = ("partial_match", 40)        # Weak similarity
    
    def __init__(self, strategy_name: str, base_confidence: int):
        self.strategy_name = strategy_name
        self.base_confidence = base_confidence


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate contact match"""
    contact_a_id: str
    contact_b_id: str
    confidence_score: float
    matching_strategy: MatchingStrategy
    matching_fields: List[str]
    conflicting_fields: List[str]
    recommended_action: str  # 'auto_merge', 'manual_review', 'ignore'
    merge_priority: str      # 'a_primary', 'b_primary', 'manual_select'
    evidence: Dict[str, Any]


@dataclass
class ContactNormalized:
    """Normalized contact data for matching"""
    id: str
    email_normalized: Optional[str]
    phone_normalized: Optional[str]
    name_normalized: str
    first_name_normalized: str
    last_name_normalized: str
    company_normalized: Optional[str]
    linkedin_normalized: Optional[str]
    email_domain: Optional[str]
    source: str
    relationship_strength: float
    last_interaction: Optional[datetime]
    interaction_count: int


class ContactDeduplicationService:
    """
    Advanced contact deduplication service with multi-source support
    
    Features:
    - Fuzzy string matching for names and companies
    - Email normalization and alias detection
    - Phone number normalization (international support)
    - Multi-level confidence scoring
    - Source-aware merging priorities
    - Configurable auto-merge thresholds
    """
    
    # Configuration constants
    AUTO_MERGE_THRESHOLD = 0.90  # 90% confidence for auto-merge
    MANUAL_REVIEW_THRESHOLD = 0.30  # Below 30% ignored as noise
    
    # Fuzzy matching thresholds
    NAME_SIMILARITY_THRESHOLD = 85  # Minimum similarity for name matching
    COMPANY_SIMILARITY_THRESHOLD = 80  # Minimum similarity for company matching
    
    # Source priority for merge conflicts (higher = preferred)
    SOURCE_PRIORITY = {
        'manual': 100,      # User-entered data highest priority
        'linkedin': 90,     # Professional network data
        'calendar': 80,     # Meeting/event data
        'gmail': 70,        # Email communication data
        'email': 70,        # Generic email source
        'import': 60,       # Bulk import data
        'unknown': 50       # Unknown source lowest priority
    }
    
    def __init__(self, db: Session):
        """
        Initialize contact deduplication service
        
        Args:
            db: Database session
        """
        self.db = db
        
    async def find_duplicates_for_contact(
        self,
        user_id: str,
        contact_id: str,
        include_low_confidence: bool = False
    ) -> List[DuplicateMatch]:
        """
        Find potential duplicates for a specific contact
        
        Args:
            user_id: User ID to scope search
            contact_id: Contact ID to find duplicates for
            include_low_confidence: Include matches below manual review threshold
            
        Returns:
            List of potential duplicate matches sorted by confidence
        """
        try:
            # Get the target contact
            target_contact = self.db.query(Contact).filter(
                and_(
                    Contact.id == contact_id,
                    Contact.user_id == user_id,
                    Contact.is_archived == False
                )
            ).first()
            
            if not target_contact:
                logger.warning(f"Contact {contact_id} not found for user {user_id}")
                return []
            
            # Get all other contacts for the user
            other_contacts = self.db.query(Contact).filter(
                and_(
                    Contact.user_id == user_id,
                    Contact.id != contact_id,
                    Contact.is_archived == False
                )
            ).all()
            
            if not other_contacts:
                return []
            
            # Normalize target contact
            target_normalized = self._normalize_contact(target_contact)
            
            # Find matches
            matches = []
            for contact in other_contacts:
                contact_normalized = self._normalize_contact(contact)
                match = self._compare_contacts(target_normalized, contact_normalized)
                
                if match and (include_low_confidence or 
                            match.confidence_score >= self.MANUAL_REVIEW_THRESHOLD):
                    matches.append(match)
            
            # Sort by confidence score (highest first)
            matches.sort(key=lambda x: x.confidence_score, reverse=True)
            
            logger.info(f"Found {len(matches)} potential duplicates for contact {contact_id}")
            return matches
            
        except Exception as e:
            logger.error(f"Error finding duplicates for contact {contact_id}: {e}")
            raise
    
    async def scan_all_duplicates(
        self,
        user_id: str,
        batch_size: int = 100,
        include_low_confidence: bool = False
    ) -> List[DuplicateMatch]:
        """
        Scan all contacts for a user to find potential duplicates
        
        Args:
            user_id: User ID to scan
            batch_size: Number of contacts to process in each batch
            include_low_confidence: Include matches below manual review threshold
            
        Returns:
            List of all potential duplicate matches
        """
        try:
            # Get all active contacts for the user
            contacts = self.db.query(Contact).filter(
                and_(
                    Contact.user_id == user_id,
                    Contact.is_archived == False
                )
            ).all()
            
            if len(contacts) < 2:
                logger.info(f"User {user_id} has fewer than 2 contacts, no duplicates possible")
                return []
            
            logger.info(f"Scanning {len(contacts)} contacts for duplicates")
            
            # Normalize all contacts
            normalized_contacts = [self._normalize_contact(contact) for contact in contacts]
            
            # Find all potential matches
            all_matches = []
            processed_pairs = set()
            
            for i, contact_a in enumerate(normalized_contacts):
                for j, contact_b in enumerate(normalized_contacts[i+1:], i+1):
                    # Avoid duplicate comparisons
                    pair_key = tuple(sorted([contact_a.id, contact_b.id]))
                    if pair_key in processed_pairs:
                        continue
                    processed_pairs.add(pair_key)
                    
                    match = self._compare_contacts(contact_a, contact_b)
                    
                    if match and (include_low_confidence or 
                                match.confidence_score >= self.MANUAL_REVIEW_THRESHOLD):
                        all_matches.append(match)
            
            # Sort by confidence score (highest first)
            all_matches.sort(key=lambda x: x.confidence_score, reverse=True)
            
            logger.info(f"Found {len(all_matches)} potential duplicate pairs")
            return all_matches
            
        except Exception as e:
            logger.error(f"Error scanning duplicates for user {user_id}: {e}")
            raise
    
    async def get_auto_merge_candidates(self, user_id: str) -> List[DuplicateMatch]:
        """
        Get contacts that can be automatically merged (≥90% confidence)
        
        Args:
            user_id: User ID to scan
            
        Returns:
            List of high-confidence duplicate matches for auto-merge
        """
        all_matches = await self.scan_all_duplicates(user_id, include_low_confidence=False)
        
        auto_merge_candidates = [
            match for match in all_matches 
            if match.confidence_score >= self.AUTO_MERGE_THRESHOLD
        ]
        
        logger.info(f"Found {len(auto_merge_candidates)} auto-merge candidates")
        return auto_merge_candidates
    
    async def get_manual_review_candidates(self, user_id: str) -> List[DuplicateMatch]:
        """
        Get contacts that require manual review (30-89% confidence)
        
        Args:
            user_id: User ID to scan
            
        Returns:
            List of medium-confidence duplicate matches for manual review
        """
        all_matches = await self.scan_all_duplicates(user_id, include_low_confidence=False)
        
        manual_review_candidates = [
            match for match in all_matches 
            if self.MANUAL_REVIEW_THRESHOLD <= match.confidence_score < self.AUTO_MERGE_THRESHOLD
        ]
        
        logger.info(f"Found {len(manual_review_candidates)} manual review candidates")
        return manual_review_candidates
    
    def _normalize_contact(self, contact: Contact) -> ContactNormalized:
        """
        Normalize contact data for consistent matching
        
        Args:
            contact: Contact ORM object
            
        Returns:
            Normalized contact data
        """
        # Email normalization
        email_normalized = None
        email_domain = None
        if contact.email:
            email_normalized = self._normalize_email(contact.email)
            email_domain = email_normalized.split('@')[1] if '@' in email_normalized else None
        
        # Phone normalization
        phone_normalized = None
        if contact.phone:
            phone_normalized = self._normalize_phone(contact.phone)
        
        # Name normalization
        name_normalized = self._normalize_name(contact.full_name or '')
        first_name_normalized = self._normalize_name(contact.first_name or '')
        last_name_normalized = self._normalize_name(contact.last_name or '')
        
        # Company normalization
        company_normalized = None
        if contact.company:
            company_normalized = self._normalize_company(contact.company)
        
        # LinkedIn normalization
        linkedin_normalized = None
        if contact.linkedin_url:
            linkedin_normalized = self._normalize_linkedin_url(contact.linkedin_url)
        
        # Calculate interaction count (placeholder - would need actual interaction query)
        interaction_count = 0  # TODO: Query actual interactions
        
        return ContactNormalized(
            id=str(contact.id),
            email_normalized=email_normalized,
            phone_normalized=phone_normalized,
            name_normalized=name_normalized,
            first_name_normalized=first_name_normalized,
            last_name_normalized=last_name_normalized,
            company_normalized=company_normalized,
            linkedin_normalized=linkedin_normalized,
            email_domain=email_domain,
            source=contact.contact_source or 'unknown',
            relationship_strength=float(contact.relationship_strength or 0.0),
            last_interaction=contact.last_interaction_at,
            interaction_count=interaction_count
        )
    
    def _compare_contacts(
        self,
        contact_a: ContactNormalized,
        contact_b: ContactNormalized
    ) -> Optional[DuplicateMatch]:
        """
        Compare two normalized contacts and determine if they're duplicates
        
        Args:
            contact_a: First normalized contact
            contact_b: Second normalized contact
            
        Returns:
            DuplicateMatch if potential duplicate found, None otherwise
        """
        matches = []
        matching_fields = []
        conflicting_fields = []
        evidence = {}
        
        # 1. Exact email match (100% confidence)
        if (contact_a.email_normalized and contact_b.email_normalized and 
            contact_a.email_normalized == contact_b.email_normalized):
            matches.append((MatchingStrategy.EXACT_EMAIL, 100))
            matching_fields.append('email')
            evidence['email_match'] = 'exact'
        
        # 2. Exact phone match (95% confidence)
        elif (contact_a.phone_normalized and contact_b.phone_normalized and 
              contact_a.phone_normalized == contact_b.phone_normalized):
            matches.append((MatchingStrategy.EXACT_PHONE, 95))
            matching_fields.append('phone')
            evidence['phone_match'] = 'exact'
        
        # 3. Exact LinkedIn match (90% confidence)
        elif (contact_a.linkedin_normalized and contact_b.linkedin_normalized and 
              contact_a.linkedin_normalized == contact_b.linkedin_normalized):
            matches.append((MatchingStrategy.EXACT_LINKEDIN, 90))
            matching_fields.append('linkedin')
            evidence['linkedin_match'] = 'exact'
        
        # 4. Fuzzy name matching with context
        else:
            name_similarity = self._calculate_name_similarity(contact_a, contact_b)
            evidence['name_similarity'] = name_similarity
            
            if name_similarity >= self.NAME_SIMILARITY_THRESHOLD:
                matching_fields.append('name')
                
                # Enhanced confidence with company context
                if (contact_a.company_normalized and contact_b.company_normalized):
                    company_similarity = fuzz.ratio(
                        contact_a.company_normalized, 
                        contact_b.company_normalized
                    )
                    evidence['company_similarity'] = company_similarity
                    
                    if company_similarity >= self.COMPANY_SIMILARITY_THRESHOLD:
                        # High confidence: same name + same company
                        confidence = min(85, (name_similarity + company_similarity) / 2)
                        matches.append((MatchingStrategy.FUZZY_NAME_COMPANY, confidence))
                        matching_fields.append('company')
                    else:
                        conflicting_fields.append('company')
                
                # Enhanced confidence with email domain context
                elif (contact_a.email_domain and contact_b.email_domain and 
                      contact_a.email_domain == contact_b.email_domain):
                    confidence = min(80, name_similarity * 0.9)
                    matches.append((MatchingStrategy.FUZZY_NAME_EMAIL_DOMAIN, confidence))
                    matching_fields.append('email_domain')
                    evidence['email_domain_match'] = True
                
                # Name similarity only
                else:
                    confidence = min(70, name_similarity * 0.8)
                    matches.append((MatchingStrategy.FUZZY_NAME_ONLY, confidence))
        
        # 5. Partial email matching (aliases, variations)
        if (contact_a.email_normalized and contact_b.email_normalized and 
            contact_a.email_normalized != contact_b.email_normalized):
            email_similarity = self._calculate_email_similarity(
                contact_a.email_normalized, contact_b.email_normalized
            )
            if email_similarity > 70:  # Threshold for email variations
                confidence = min(60, email_similarity * 0.7)
                matches.append((MatchingStrategy.PARTIAL_EMAIL, confidence))
                matching_fields.append('email_partial')
                evidence['email_similarity'] = email_similarity
        
        # Return best match if any found
        if not matches:
            return None
        
        # Get the highest confidence match
        best_match = max(matches, key=lambda x: x[1])
        strategy, confidence_score = best_match
        
        # Determine recommended action
        if confidence_score >= self.AUTO_MERGE_THRESHOLD * 100:
            recommended_action = 'auto_merge'
        elif confidence_score >= self.MANUAL_REVIEW_THRESHOLD * 100:
            recommended_action = 'manual_review'
        else:
            recommended_action = 'ignore'
        
        # Determine merge priority based on data quality and source
        merge_priority = self._determine_merge_priority(contact_a, contact_b)
        
        return DuplicateMatch(
            contact_a_id=contact_a.id,
            contact_b_id=contact_b.id,
            confidence_score=confidence_score / 100.0,  # Convert to 0.0-1.0 scale
            matching_strategy=strategy,
            matching_fields=matching_fields,
            conflicting_fields=conflicting_fields,
            recommended_action=recommended_action,
            merge_priority=merge_priority,
            evidence=evidence
        )
    
    def _calculate_name_similarity(
        self,
        contact_a: ContactNormalized,
        contact_b: ContactNormalized
    ) -> float:
        """Calculate similarity between contact names"""
        # Try different name combinations for best match
        similarities = []
        
        # Full name comparison
        if contact_a.name_normalized and contact_b.name_normalized:
            similarities.append(fuzz.ratio(contact_a.name_normalized, contact_b.name_normalized))
        
        # First + Last name comparison
        if (contact_a.first_name_normalized and contact_a.last_name_normalized and
            contact_b.first_name_normalized and contact_b.last_name_normalized):
            name_a = f"{contact_a.first_name_normalized} {contact_a.last_name_normalized}"
            name_b = f"{contact_b.first_name_normalized} {contact_b.last_name_normalized}"
            similarities.append(fuzz.ratio(name_a, name_b))
        
        # Cross-comparison (first name vs full name, etc.)
        if contact_a.first_name_normalized and contact_b.name_normalized:
            similarities.append(fuzz.partial_ratio(contact_a.first_name_normalized, contact_b.name_normalized))
        
        if contact_b.first_name_normalized and contact_a.name_normalized:
            similarities.append(fuzz.partial_ratio(contact_b.first_name_normalized, contact_a.name_normalized))
        
        return max(similarities) if similarities else 0.0
    
    def _calculate_email_similarity(self, email_a: str, email_b: str) -> float:
        """Calculate similarity between email addresses for alias detection"""
        # Extract username parts
        username_a = email_a.split('@')[0]
        username_b = email_b.split('@')[0]
        
        # Check for common alias patterns
        # Remove dots, underscores, numbers
        clean_a = re.sub(r'[._0-9]', '', username_a.lower())
        clean_b = re.sub(r'[._0-9]', '', username_b.lower())
        
        if clean_a == clean_b:
            return 90.0  # High similarity for alias patterns
        
        # Fuzzy match on cleaned usernames
        return fuzz.ratio(clean_a, clean_b)
    
    def _determine_merge_priority(
        self,
        contact_a: ContactNormalized,
        contact_b: ContactNormalized
    ) -> str:
        """Determine which contact should be primary in a merge"""
        score_a = self._calculate_contact_quality_score(contact_a)
        score_b = self._calculate_contact_quality_score(contact_b)
        
        if score_a > score_b:
            return 'a_primary'
        elif score_b > score_a:
            return 'b_primary'
        else:
            return 'manual_select'
    
    def _calculate_contact_quality_score(self, contact: ContactNormalized) -> float:
        """Calculate a quality score for contact data completeness and reliability"""
        score = 0.0
        
        # Source reliability
        score += self.SOURCE_PRIORITY.get(contact.source, 50)
        
        # Data completeness
        if contact.email_normalized:
            score += 20
        if contact.phone_normalized:
            score += 15
        if contact.name_normalized:
            score += 15
        if contact.company_normalized:
            score += 10
        if contact.linkedin_normalized:
            score += 10
        
        # Relationship strength
        score += contact.relationship_strength * 20
        
        # Recent interaction
        if contact.last_interaction:
            days_ago = (datetime.now(timezone.utc) - contact.last_interaction).days
            if days_ago < 30:
                score += 10
            elif days_ago < 90:
                score += 5
        
        # Interaction count
        score += min(contact.interaction_count * 2, 20)
        
        return score
    
    def _normalize_email(self, email: str) -> str:
        """Normalize email address for consistent matching"""
        if not email:
            return ''
        
        email = email.lower().strip()
        
        # Handle Gmail alias patterns (dots and plus signs)
        if '@gmail.com' in email:
            username, domain = email.split('@')
            # Remove dots from username
            username = username.replace('.', '')
            # Remove everything after + sign
            if '+' in username:
                username = username.split('+')[0]
            email = f"{username}@{domain}"
        
        return email
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for consistent matching"""
        if not phone or not PHONE_PARSING_AVAILABLE:
            # Basic normalization if phonenumbers not available
            return re.sub(r'[^\d]', '', phone)
        
        try:
            # Parse phone number (assume US if no country code)
            parsed = phonenumbers.parse(phone, "US")
            if phonenumbers.is_valid_number(parsed):
                # Return in E164 format for consistency
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except NumberParseException:
            pass
        
        # Fallback to basic normalization
        return re.sub(r'[^\d]', '', phone)
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for consistent matching"""
        if not name:
            return ''
        
        # Convert to lowercase, remove extra spaces
        name = re.sub(r'\s+', ' ', name.lower().strip())
        
        # Remove common prefixes/suffixes
        prefixes = ['mr.', 'mrs.', 'ms.', 'dr.', 'prof.']
        suffixes = ['jr.', 'sr.', 'ii', 'iii', 'iv']
        
        words = name.split()
        words = [w for w in words if w not in prefixes and w not in suffixes]
        
        return ' '.join(words)
    
    def _normalize_company(self, company: str) -> str:
        """Normalize company name for consistent matching"""
        if not company:
            return ''
        
        company = company.lower().strip()
        
        # Remove common company suffixes
        suffixes = ['inc.', 'inc', 'llc', 'ltd.', 'ltd', 'corp.', 'corp', 'co.', 'co']
        words = company.split()
        
        # Remove suffix if it's the last word
        if words and words[-1] in suffixes:
            words = words[:-1]
        
        return ' '.join(words)
    
    def _normalize_linkedin_url(self, url: str) -> str:
        """Normalize LinkedIn URL for consistent matching"""
        if not url:
            return ''
        
        # Extract username from LinkedIn URL
        url = url.lower().strip()
        
        # Handle different LinkedIn URL formats
        patterns = [
            r'linkedin\.com/in/([^/?]+)',
            r'linkedin\.com/pub/([^/?]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return url 