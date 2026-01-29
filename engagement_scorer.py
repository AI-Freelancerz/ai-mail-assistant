"""
Engagement Scoring & List Segmentation

Helps identify and prioritize engaged users for better deliverability.
Send to engaged users first during warm-up for higher open rates.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


class EngagementScorer:
    '''Score and segment contact lists by engagement level'''
    
    TIER_1_DAYS = 30   # Highly engaged (opened/clicked recently)
    TIER_2_DAYS = 90   # Moderately engaged  
    TIER_3_DAYS = 180  # Minimally engaged
    
    def __init__(self):
        pass
    
    def score_contacts(
        self,
        contacts: List[Dict],
        engagement_data: Dict[str, datetime] = None
    ) -> List[Dict]:
        '''
        Add engagement scores to contacts.
        
        Args:
            contacts: List of contact dicts with 'email' key
            engagement_data: Dict of {email: last_engagement_date}
            
        Returns:
            Contacts with added 'engagement_tier' and 'engagement_score'
        '''
        if not engagement_data:
            # If no engagement data, assign all to Tier 3 (neutral)
            for contact in contacts:
                contact['engagement_tier'] = 3
                contact['engagement_score'] = 50
                contact['engagement_label'] = 'Unknown'
            return contacts
        
        now = datetime.now()
        
        for contact in contacts:
            email = contact.get('email', '').lower()
            last_engagement = engagement_data.get(email)
            
            if not last_engagement:
                # Never engaged
                contact['engagement_tier'] = 4
                contact['engagement_score'] = 0
                contact['engagement_label'] = 'Never Engaged'
                contact['days_since_engagement'] = 999
            else:
                days_since = (now - last_engagement).days
                contact['days_since_engagement'] = days_since
                
                # Assign tier
                if days_since <= self.TIER_1_DAYS:
                    contact['engagement_tier'] = 1
                    contact['engagement_score'] = 100 - (days_since / self.TIER_1_DAYS * 20)
                    contact['engagement_label'] = 'Highly Engaged'
                elif days_since <= self.TIER_2_DAYS:
                    contact['engagement_tier'] = 2
                    contact['engagement_score'] = 80 - ((days_since - self.TIER_1_DAYS) / (self.TIER_2_DAYS - self.TIER_1_DAYS) * 30)
                    contact['engagement_label'] = 'Moderately Engaged'
                elif days_since <= self.TIER_3_DAYS:
                    contact['engagement_tier'] = 3
                    contact['engagement_score'] = 50 - ((days_since - self.TIER_2_DAYS) / (self.TIER_3_DAYS - self.TIER_2_DAYS) * 30)
                    contact['engagement_label'] = 'Minimally Engaged'
                else:
                    contact['engagement_tier'] = 4
                    contact['engagement_score'] = 20
                    contact['engagement_label'] = 'Cold/Inactive'
        
        return contacts
    
    def segment_by_tier(self, contacts: List[Dict]) -> Dict[int, List[Dict]]:
        '''
        Segment contacts into tiers.
        
        Returns:
            Dict of {tier_number: [contacts]}
        '''
        tiers = {1: [], 2: [], 3: [], 4: []}
        
        for contact in contacts:
            tier = contact.get('engagement_tier', 3)
            tiers[tier].append(contact)
        
        return tiers
    
    def get_engagement_summary(self, contacts: List[Dict]) -> Dict:
        '''Get summary stats of engagement distribution'''
        total = len(contacts)
        
        tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for contact in contacts:
            tier = contact.get('engagement_tier', 3)
            tier_counts[tier] += 1
        
        return {
            'total_contacts': total,
            'tier_1_count': tier_counts[1],
            'tier_1_pct': (tier_counts[1] / total * 100) if total > 0 else 0,
            'tier_2_count': tier_counts[2],
            'tier_2_pct': (tier_counts[2] / total * 100) if total > 0 else 0,
            'tier_3_count': tier_counts[3],
            'tier_3_pct': (tier_counts[3] / total * 100) if total > 0 else 0,
            'tier_4_count': tier_counts[4],
            'tier_4_pct': (tier_counts[4] / total * 100) if total > 0 else 0,
            'engaged_count': tier_counts[1] + tier_counts[2],  # Tier 1 + 2
            'engaged_pct': ((tier_counts[1] + tier_counts[2]) / total * 100) if total > 0 else 0,
        }
    
    def filter_by_engagement(
        self,
        contacts: List[Dict],
        min_tier: int = 3,
        exclude_never_engaged: bool = True
    ) -> Tuple[List[Dict], List[Dict]]:
        '''
        Filter contacts by minimum engagement level.
        
        Args:
            contacts: Scored contacts
            min_tier: Minimum tier to include (1=best, 4=worst)
            exclude_never_engaged: Remove tier 4 (never engaged)
            
        Returns:
            Tuple of (included_contacts, excluded_contacts)
        '''
        included = []
        excluded = []
        
        for contact in contacts:
            tier = contact.get('engagement_tier', 3)
            
            # Exclude never-engaged if requested
            if exclude_never_engaged and tier == 4:
                excluded.append(contact)
                continue
            
            # Include if tier meets minimum
            if tier <= min_tier:
                included.append(contact)
            else:
                excluded.append(contact)
        
        logger.info(
            f'Filtered by engagement: {len(included)} included, '
            f'{len(excluded)} excluded'
        )
        
        return included, excluded
    
    def recommend_warmup_list(
        self,
        contacts: List[Dict],
        warmup_day: int
    ) -> List[Dict]:
        '''
        Recommend which contacts to send to based on warm-up day.
        
        Strategy:
        - Days 1-3: Only Tier 1 (highly engaged)
        - Days 4-7: Tier 1 + Tier 2 (moderately engaged)
        - Days 8+: Tier 1 + Tier 2 + Tier 3 (all engaged)
        - Never send to Tier 4 during warm-up
        
        Returns:
            Filtered list of contacts appropriate for this warm-up day
        '''
        if warmup_day <= 3:
            # First 3 days: most engaged only
            recommended = [c for c in contacts if c.get('engagement_tier', 4) == 1]
            logger.info(f'Warm-up Day {warmup_day}: Recommending Tier 1 only ({len(recommended)} contacts)')
        
        elif warmup_day <= 7:
            # Days 4-7: add moderately engaged
            recommended = [c for c in contacts if c.get('engagement_tier', 4) in [1, 2]]
            logger.info(f'Warm-up Day {warmup_day}: Recommending Tier 1+2 ({len(recommended)} contacts)')
        
        else:
            # Days 8+: all engaged users
            recommended = [c for c in contacts if c.get('engagement_tier', 4) in [1, 2, 3]]
            logger.info(f'Warm-up Day {warmup_day}: Recommending Tier 1+2+3 ({len(recommended)} contacts)')
        
        return recommended
    
    def sort_by_engagement(self, contacts: List[Dict]) -> List[Dict]:
        '''Sort contacts by engagement score (highest first)'''
        return sorted(
            contacts,
            key=lambda c: c.get('engagement_score', 0),
            reverse=True
        )


def get_engagement_scorer() -> EngagementScorer:
    '''Get engagement scorer instance'''
    return EngagementScorer()
