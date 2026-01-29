"""
Email Queue Processor

Background worker that processes the email queue:
- Monitors queue for ready jobs
- Sends emails respecting rate limits
- Handles retries and errors
- Updates campaign progress

Run this continuously in background or as scheduled task.
"""

import logging
import time
from datetime import datetime
from typing import Dict
from email_queue import get_queue_manager, JobStatus
from email_tool import send_email_message
from sending_limits_tracker import get_limits_tracker
from suppression_list_manager import get_suppression_manager
import config

logger = logging.getLogger(__name__)


class QueueProcessor:
    """Process emails from the queue"""
    
    def __init__(self):
        self.queue_manager = get_queue_manager()
        self.limits_tracker = get_limits_tracker()
        self.suppression_manager = get_suppression_manager()
        self.is_running = False
    
    def process_once(self) -> Dict:
        """
        Process queue one time - send all ready emails that fit within limits.
        
        Returns:
            Dict with stats: sent, failed, skipped, remaining
        """
        stats = {
            'sent': 0,
            'failed': 0,
            'skipped': 0,
            'remaining': 0,
            'errors': []
        }
        
        # Check if we can send any emails now
        can_send, reason = self.limits_tracker.can_send()
        if not can_send:
            logger.info(f"[QUEUE_PROCESSOR] Cannot send now: {reason}")
            stats['skipped'] = len(self.queue_manager.get_ready_jobs())
            stats['remaining'] = stats['skipped']
            return stats
        
        # Get ready jobs
        ready_jobs = self.queue_manager.get_ready_jobs(limit=100)
        
        if not ready_jobs:
            logger.debug("[QUEUE_PROCESSOR] No jobs ready for sending")
            return stats
        
        logger.info(f"[QUEUE_PROCESSOR] Found {len(ready_jobs)} ready jobs")
        
        # Process jobs one by one
        for job in ready_jobs:
            # Check limits before each send
            can_send, reason = self.limits_tracker.can_send()
            if not can_send:
                logger.info(f"[QUEUE_PROCESSOR] Stopping: {reason}")
                stats['remaining'] = len(ready_jobs) - stats['sent'] - stats['failed']
                break
            
            # Check if email is suppressed
            if self.suppression_manager.is_suppressed(job['to_email']):
                logger.info(f"[QUEUE_PROCESSOR] Skipping suppressed email: {job['to_email']}")
                self.queue_manager.mark_job_failed(
                    job['id'],
                    "Email address is in suppression list"
                )
                stats['skipped'] += 1
                continue
            
            # Send the email
            success = self._send_job(job)
            
            if success:
                stats['sent'] += 1
                self.limits_tracker.record_sends(1)
                
                # Rate limiting delay
                time.sleep(config.EMAIL_MIN_SEND_INTERVAL_SECONDS)
            else:
                stats['failed'] += 1
        
        logger.info(
            f"[QUEUE_PROCESSOR] Processed {stats['sent']} sent, "
            f"{stats['failed']} failed, {stats['skipped']} skipped, "
            f"{stats['remaining']} remaining"
        )
        
        return stats
    
    def _send_job(self, job: Dict) -> bool:
        """
        Send a single email job.
        
        Returns:
            True if successful, False if failed
        """
        job_id = job['id']
        
        try:
            # Mark as sending
            self.queue_manager.mark_job_sending(job_id)
            
            # Send email
            result = send_email_message(
                sender_email=job['sender_email'],
                sender_name=job['sender_name'],
                to_email=job['to_email'],
                to_name=job['to_name'],
                subject=job['subject'],
                body=job['body'],
                attachments=job.get('attachments')
            )
            
            # Check result
            if result and result.get('status') == 'success':
                self.queue_manager.mark_job_completed(job_id)
                logger.info(f"[QUEUE_PROCESSOR] Sent: {job['to_email']}")
                return True
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result'
                self.queue_manager.mark_job_failed(job_id, error_msg)
                logger.error(f"[QUEUE_PROCESSOR] Failed: {job['to_email']} - {error_msg}")
                return False
                
        except Exception as e:
            error_msg = str(e)
            self.queue_manager.mark_job_failed(job_id, error_msg)
            logger.error(f"[QUEUE_PROCESSOR] Exception sending {job['to_email']}: {e}")
            return False
    
    def run_continuous(self, check_interval: int = None):
        """
        Run processor continuously in background.
        
        Args:
            check_interval: Seconds between queue checks (default from config)
        """
        if check_interval is None:
            check_interval = config.EMAIL_QUEUE_CHECK_INTERVAL
        
        self.is_running = True
        logger.info(f"[QUEUE_PROCESSOR] Starting continuous mode (check every {check_interval}s)")
        
        try:
            while self.is_running:
                try:
                    stats = self.process_once()
                    
                    # If we sent something, process again immediately
                    # Otherwise wait for check interval
                    if stats['sent'] > 0:
                        time.sleep(config.EMAIL_MIN_SEND_INTERVAL_SECONDS)
                    else:
                        time.sleep(check_interval)
                        
                except KeyboardInterrupt:
                    logger.info("[QUEUE_PROCESSOR] Received interrupt signal, stopping...")
                    break
                except Exception as e:
                    logger.error(f"[QUEUE_PROCESSOR] Error in continuous loop: {e}")
                    time.sleep(check_interval)
        
        finally:
            self.is_running = False
            logger.info("[QUEUE_PROCESSOR] Stopped")
    
    def stop(self):
        """Stop continuous processing"""
        self.is_running = False


# Convenience function for direct use
def process_queue_once():
    """Process the queue one time"""
    processor = QueueProcessor()
    return processor.process_once()


if __name__ == "__main__":
    # When run directly, start continuous processing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    processor = QueueProcessor()
    processor.run_continuous()
