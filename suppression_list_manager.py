"""
Suppression List Manager - Email Deliverability Module

Manages the suppression list to prevent sending to:
- Hard bounces (invalid addresses)
- Spam complaints
- Unsubscribes
- Blocked addresses

CRITICAL for maintaining sender reputation and compliance.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Tuple
import config

logger = logging.getLogger(__name__)


class SuppressionListManager:
    """Manages email suppression list for deliverability compliance"""
    
    def __init__(self, suppression_file: str = None):
        self.suppression_file = suppression_file or config.EMAIL_SUPPRESSION_LIST_PATH
        self.suppression_path = Path(self.suppression_file)
        self._ensure_suppression_file_exists()
        
    def _ensure_suppression_file_exists(self):
        """Create suppression list file if it doesn't exist"""
        if not self.suppression_path.exists():
            self.suppression_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.suppression_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['email', 'reason', 'timestamp', 'campaign_id', 'details'])
            logger.info(f"Created new suppression list: {self.suppression_path}")
    
    def load_suppression_set(self) -> Set[str]:
        """
        Load suppressed email addresses as a set for fast lookups.
        
        Returns:
            Set of lowercase email addresses that should never be emailed
        """
        suppressed = set()
        
        try:
            with open(self.suppression_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get('email', '').strip().lower()
                    if email:
                        suppressed.add(email)
            
            logger.info(f"Loaded {len(suppressed)} suppressed addresses")
            return suppressed
            
        except Exception as e:
            logger.error(f"Error loading suppression list: {e}")
            return set()
    
    def add_to_suppression(
        self, 
        email: str, 
        reason: str, 
        campaign_id: str = "", 
        details: str = ""
    ) -> bool:
        """
        Add an email address to the suppression list.
        
        Args:
            email: Email address to suppress
            reason: Reason for suppression (hardbounce, spam, unsubscribe, blocked)
            campaign_id: Optional campaign ID that triggered suppression
            details: Optional additional details (bounce reason, etc.)
            
        Returns:
            True if added successfully, False if already suppressed or error
        """
        email = email.strip().lower()
        
        if not email:
            return False
        
        # Check if already suppressed
        suppressed = self.load_suppression_set()
        if email in suppressed:
            logger.debug(f"Email already suppressed: {email}")
            return False
        
        try:
            # Append to suppression list
            with open(self.suppression_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    email,
                    reason,
                    datetime.now().isoformat(),
                    campaign_id,
                    details
                ])
            
            logger.info(f"Added to suppression list: {email} (reason: {reason})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding {email} to suppression list: {e}")
            return False
    
    def add_bulk_to_suppression(self, emails_with_reasons: List[Dict]) -> Tuple[int, int]:
        """
        Add multiple emails to suppression list at once.
        
        Args:
            emails_with_reasons: List of dicts with keys: email, reason, campaign_id, details
            
        Returns:
            Tuple of (added_count, skipped_count)
        """
        suppressed = self.load_suppression_set()
        added = 0
        skipped = 0
        
        try:
            with open(self.suppression_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                for item in emails_with_reasons:
                    email = item.get('email', '').strip().lower()
                    
                    if not email or email in suppressed:
                        skipped += 1
                        continue
                    
                    writer.writerow([
                        email,
                        item.get('reason', ''),
                        datetime.now().isoformat(),
                        item.get('campaign_id', ''),
                        item.get('details', '')
                    ])
                    
                    suppressed.add(email)  # Track to avoid duplicates in same batch
                    added += 1
            
            logger.info(f"Bulk suppression: added {added}, skipped {skipped}")
            return added, skipped
            
        except Exception as e:
            logger.error(f"Error in bulk suppression add: {e}")
            return added, skipped
    
    def is_suppressed(self, email: str) -> bool:
        """
        Check if an email address is suppressed.
        
        Args:
            email: Email address to check
            
        Returns:
            True if email is in suppression list
        """
        email = email.strip().lower()
        suppressed = self.load_suppression_set()
        return email in suppressed
    
    def filter_contacts(self, contacts: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter a contact list, removing suppressed addresses.
        
        Args:
            contacts: List of contact dicts (must have 'email' key)
            
        Returns:
            Tuple of (clean_contacts, suppressed_contacts)
        """
        suppressed_set = self.load_suppression_set()
        
        clean = []
        suppressed_found = []
        
        for contact in contacts:
            email = contact.get('email', '').strip().lower()
            
            if email in suppressed_set:
                suppressed_found.append(contact)
            else:
                clean.append(contact)
        
        if suppressed_found:
            logger.warning(
                f"Filtered out {len(suppressed_found)} suppressed addresses "
                f"from {len(contacts)} contacts"
            )
        
        return clean, suppressed_found
    
    def get_suppression_stats(self) -> Dict:
        """
        Get statistics about the suppression list.
        
        Returns:
            Dict with counts by reason and total
        """
        stats = {
            'total': 0,
            'hardbounce': 0,
            'spam': 0,
            'unsubscribe': 0,
            'blocked': 0,
            'other': 0
        }
        
        try:
            with open(self.suppression_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats['total'] += 1
                    reason = row.get('reason', '').lower()
                    
                    if 'bounce' in reason:
                        stats['hardbounce'] += 1
                    elif 'spam' in reason:
                        stats['spam'] += 1
                    elif 'unsubscribe' in reason:
                        stats['unsubscribe'] += 1
                    elif 'block' in reason:
                        stats['blocked'] += 1
                    else:
                        stats['other'] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting suppression stats: {e}")
            return stats
    
    def export_suppression_list(self, output_file: str = None) -> bool:
        """
        Export suppression list to a different file (for backups or sharing).
        
        Args:
            output_file: Path to export to (default: suppression_list_backup.csv)
            
        Returns:
            True if successful
        """
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"suppression_list_backup_{timestamp}.csv"
        
        try:
            import shutil
            shutil.copy2(self.suppression_path, output_file)
            logger.info(f"Exported suppression list to: {output_file}")
            return True
        except Exception as e:
            logger.error(f"Error exporting suppression list: {e}")
            return False


# Singleton instance for global access
_suppression_manager = None

def get_suppression_manager() -> SuppressionListManager:
    """Get or create the global suppression list manager instance"""
    global _suppression_manager
    if _suppression_manager is None:
        _suppression_manager = SuppressionListManager()
    return _suppression_manager
