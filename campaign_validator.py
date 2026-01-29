"""
Pre-Flight Validation Checklist

Validates campaign readiness before sending.
Helps prevent deliverability issues by checking configuration.
"""

import logging
from typing import Dict, List, Tuple
from datetime import datetime
import config
from sending_limits_tracker import get_limits_tracker
from suppression_list_manager import get_suppression_manager
from email_utils import validate_email_content, is_gmail_address
import re

logger = logging.getLogger(__name__)


class CampaignValidator:
    '''Validates campaigns before sending'''
    
    def __init__(self):
        self.limits_tracker = get_limits_tracker()
        self.suppression_manager = get_suppression_manager()
    
    def validate_campaign(
        self,
        sender_email: str,
        subject: str,
        body: str,
        contacts: List[Dict],
        check_limits: bool = True
    ) -> Tuple[bool, List[str], List[str]]:
        '''
        Run all validation checks.
        
        Returns:
            Tuple of (is_valid, errors, warnings)
            - is_valid: False if any blocking errors
            - errors: List of blocking issues
            - warnings: List of non-blocking concerns
        '''
        errors = []
        warnings = []
        
        # 1. Domain Authentication
        domain_errors, domain_warnings = self._check_domain(sender_email)
        errors.extend(domain_errors)
        warnings.extend(domain_warnings)
        
        # 2. Content Validation
        content_errors, content_warnings = self._check_content(subject, body)
        errors.extend(content_errors)
        warnings.extend(content_warnings)
        
        # 3. List Quality
        list_errors, list_warnings = self._check_list_quality(contacts)
        errors.extend(list_errors)
        warnings.extend(list_warnings)
        
        # 4. Sending Limits
        if check_limits:
            limit_errors, limit_warnings = self._check_limits(len(contacts))
            errors.extend(limit_errors)
            warnings.extend(limit_warnings)
        
        # 5. Configuration
        config_errors, config_warnings = self._check_configuration()
        errors.extend(config_errors)
        warnings.extend(config_warnings)
        
        is_valid = len(errors) == 0
        
        return is_valid, errors, warnings
    
    def _check_domain(self, sender_email: str) -> Tuple[List[str], List[str]]:
        '''Validate sender domain'''
        errors = []
        warnings = []
        
        if not sender_email:
            errors.append('❌ No sender email configured')
            return errors, warnings
        
        # Check for Gmail (blocking error)
        if config.REQUIRE_DOMAIN_VERIFICATION and is_gmail_address(sender_email):
            errors.append(
                f'❌ Cannot send from Gmail ({sender_email}). '
                'Gmail prohibits bulk sending. Configure verified domain.'
            )
        
        # Check domain matches config
        if '@' in sender_email:
            domain = sender_email.split('@')[1]
            if config.SENDER_DOMAIN and domain != config.SENDER_DOMAIN:
                warnings.append(
                    f'⚠️ Sender domain ({domain}) differs from configured domain '
                    f'({config.SENDER_DOMAIN})'
                )
        
        # Check domain age
        domain_age = self.limits_tracker.get_domain_age_days()
        if domain_age == 0:
            warnings.append(
                '⚠️ Domain verification date not set. '
                'Run setup_deliverability.py to configure.'
            )
        
        return errors, warnings
    
    def _check_content(self, subject: str, body: str) -> Tuple[List[str], List[str]]:
        '''Validate email content'''
        errors = []
        warnings = []
        
        # Run content validation
        is_valid, content_warnings = validate_email_content(subject, body)
        
        if not is_valid:
            errors.append('❌ Content validation failed')
        
        # All content issues are warnings unless blocking
        for warning in content_warnings:
            if 'empty' in warning.lower() or 'missing' in warning.lower():
                errors.append(f'❌ {warning}')
            else:
                warnings.append(f'⚠️ {warning}')
        
        # Check for unsubscribe link
        if config.EMAIL_REQUIRE_LIST_UNSUBSCRIBE:
            has_unsubscribe = (
                'unsubscribe' in body.lower() or
                '{{unsubscribe}}' in body or
                '{{ unsubscribe }}' in body
            )
            if not has_unsubscribe:
                warnings.append(
                    '⚠️ No unsubscribe link found in body. '
                    'Add {{unsubscribe}} merge tag.'
                )
        
        return errors, warnings
    
    def _check_list_quality(self, contacts: List[Dict]) -> Tuple[List[str], List[str]]:
        '''Validate contact list quality'''
        errors = []
        warnings = []
        
        if not contacts:
            errors.append('❌ Contact list is empty')
            return errors, warnings
        
        # Check for suppressed addresses
        suppressed_count = 0
        for contact in contacts:
            email = contact.get('email', '')
            if self.suppression_manager.is_suppressed(email):
                suppressed_count += 1
        
        if suppressed_count > 0:
            warnings.append(
                f'⚠️ List contains {suppressed_count} suppressed addresses. '
                'These will be filtered out automatically.'
            )
        
        # Check list size vs daily limit
        daily_limit = self.limits_tracker.get_daily_limit()
        if len(contacts) > daily_limit * 10:
            warnings.append(
                f'⚠️ Large list ({len(contacts)} contacts) will take multiple days. '
                f'Current daily limit: {daily_limit}'
            )
        
        # Check for duplicates
        emails = [c.get('email', '').lower() for c in contacts]
        unique_emails = set(emails)
        if len(emails) != len(unique_emails):
            duplicate_count = len(emails) - len(unique_emails)
            warnings.append(
                f'⚠️ List contains {duplicate_count} duplicate email addresses'
            )
        
        return errors, warnings
    
    def _check_limits(self, contact_count: int) -> Tuple[List[str], List[str]]:
        '''Check if sending limits allow this campaign'''
        errors = []
        warnings = []
        
        # Check if we can send now
        can_send, reason = self.limits_tracker.can_send(count=contact_count)
        
        if not can_send:
            if 'daily limit reached' in reason.lower():
                warnings.append(f'⚠️ {reason} Campaign will start tomorrow.')
            elif 'warm-up' in reason.lower():
                warnings.append(f'⚠️ {reason}')
            else:
                warnings.append(f'⚠️ {reason}')
        
        # Check warm-up status
        domain_age = self.limits_tracker.get_domain_age_days()
        if domain_age < config.EMAIL_WARMUP_DAYS:
            daily_limit = self.limits_tracker.get_daily_limit()
            warnings.append(
                f'⚠️ In warm-up period (Day {domain_age + 1}/{config.EMAIL_WARMUP_DAYS}). '
                f'Daily limit: {daily_limit} emails.'
            )
        
        return errors, warnings
    
    def _check_configuration(self) -> Tuple[List[str], List[str]]:
        '''Validate system configuration'''
        errors = []
        warnings = []
        
        # Check essential configs
        if not config.BREVO_API_KEY:
            errors.append('❌ Brevo API key not configured')
        
        if not config.SENDER_EMAIL:
            errors.append('❌ Sender email not configured')
        
        # Check recommended settings
        if not config.EMAIL_REQUIRE_PLAIN_TEXT:
            warnings.append(
                '⚠️ Plain-text emails not required. '
                'Recommended for better deliverability.'
            )
        
        if not config.EMAIL_REQUIRE_LIST_UNSUBSCRIBE:
            warnings.append(
                '⚠️ List-Unsubscribe header not required. '
                'Recommended for Gmail/Yahoo compliance.'
            )
        
        return errors, warnings
    
    def format_validation_report(
        self,
        is_valid: bool,
        errors: List[str],
        warnings: List[str]
    ) -> str:
        '''Format validation results as human-readable report'''
        report = []
        
        if is_valid:
            report.append('✅ CAMPAIGN VALIDATION PASSED')
        else:
            report.append('❌ CAMPAIGN VALIDATION FAILED')
        
        report.append('')
        
        if errors:
            report.append('BLOCKING ERRORS (must fix):')
            for error in errors:
                report.append(f'  {error}')
            report.append('')
        
        if warnings:
            report.append('WARNINGS (recommend fixing):')
            for warning in warnings:
                report.append(f'  {warning}')
            report.append('')
        
        if is_valid and not warnings:
            report.append('No issues found. Campaign is ready to send!')
        elif is_valid and warnings:
            report.append(f'Campaign can proceed but has {len(warnings)} warnings.')
        else:
            report.append(f'Cannot send until {len(errors)} error(s) are fixed.')
        
        return '\n'.join(report)


def get_campaign_validator() -> CampaignValidator:
    '''Get campaign validator instance'''
    return CampaignValidator()
