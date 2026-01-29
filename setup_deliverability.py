"""
Email Deliverability Setup CLI

Helper script for initial configuration and testing.
"""

import sys
from datetime import datetime
from suppression_list_manager import get_suppression_manager
from sending_limits_tracker import get_limits_tracker
from email_utils import validate_email_content, is_safe_send_time
from email_queue import get_queue_manager
import config


def print_header(title):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60 + "\n")


def setup_domain_verification():
    """Set domain verification date to start warm-up"""
    print_header("Domain Verification Setup")
    
    print("Setting domain verification date starts the warm-up schedule.")
    print(f"Current sender: {config.SENDER_EMAIL}")
    print(f"Current domain: {config.SENDER_DOMAIN}")
    print()
    
    confirm = input("Is your domain verified in Brevo? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("\n⚠️  Please verify your domain in Brevo dashboard first:")
        print("   1. Go to Brevo → Settings → Senders & IP")
        print("   2. Add your domain")
        print("   3. Add DNS records (SPF, DKIM, DMARC)")
        print("   4. Wait 24-48h for DNS propagation")
        print("   5. Click 'Verify' in Brevo dashboard")
        print("   6. Come back here when verified")
        return
    
    tracker = get_limits_tracker()
    tracker.set_domain_verified_date()
    
    print("\n✅ Domain verification date set!")
    print(f"   Warm-up starts TODAY (Day 1)")
    print(f"   Daily limit: 50 emails")
    print()


def show_current_status():
    """Show current sending status and limits"""
    print_header("Current Status")
    
    tracker = get_limits_tracker()
    summary = tracker.get_limits_summary()
    
    print(f"📅 Domain Age: {summary['domain_age_days']} days")
    
    if summary['is_warmup_period']:
        print(f"🔥 Warm-up Status: Day {summary['warmup_day']}")
    else:
        print(f"✅ Warm-up: {summary['warmup_day']}")
    
    print()
    print(f"📊 Daily Limits:")
    print(f"   Limit:     {summary['daily_limit']:,} emails")
    print(f"   Sent:      {summary['daily_sent']:,} emails")
    print(f"   Remaining: {summary['daily_remaining']:,} emails")
    print(f"   Usage:     {summary['daily_usage_pct']:.1f}%")
    
    print()
    print(f"⏰ Hourly Limits:")
    print(f"   Limit:     {summary['hourly_limit']:,} emails/hour")
    print(f"   Sent:      {summary['hourly_sent']:,} emails")
    print(f"   Remaining: {summary['hourly_remaining']:,} emails")
    print(f"   Usage:     {summary['hourly_usage_pct']:.1f}%")
    
    print()
    is_safe, reason = is_safe_send_time()
    if is_safe:
        print(f"✅ Send Time: {reason}")
    else:
        print(f"❌ Send Time: {reason}")
    
    print()
    can_send, reason = tracker.can_send()
    if can_send:
        print(f"✅ Can Send: Yes")
    else:
        print(f"❌ Can Send: {reason}")
    
    # Suppression stats
    suppression = get_suppression_manager()
    stats = suppression.get_suppression_stats()
    
    print()
    print(f"🛡️  Suppression List:")
    print(f"   Total:           {stats['total']:,} addresses")
    print(f"   Hard Bounces:    {stats['hardbounce']:,}")
    print(f"   Spam Complaints: {stats['spam']:,}")
    print(f"   Unsubscribes:    {stats['unsubscribe']:,}")
    print(f"   Blocked:         {stats['blocked']:,}")
    print(f"   Other:           {stats['other']:,}")
    
    print()


def show_campaigns():
    """Show all campaigns and their status"""
    print_header("Campaign Status")
    
    queue = get_queue_manager()
    campaigns = queue.get_all_campaigns()
    
    if not campaigns:
        print("No campaigns found.")
        return
    
    for camp in campaigns:
        status_icon = {
            'pending': '⏳',
            'scheduled': '📅',
            'sending': '📤',
            'completed': '✅',
            'failed': '❌',
            'paused': '⏸️',
            'cancelled': '🚫'
        }.get(camp['status'], '❓')
        
        print(f"{status_icon} {camp['name']}")
        print(f"   ID: {camp['id']}")
        print(f"   Status: {camp['status']}")
        print(f"   Progress: {camp['sent_count']}/{camp['total_contacts']} sent ({camp['progress_pct']:.1f}%)")
        print(f"   Failed: {camp['failed_count']}")
        print(f"   Pending: {camp['pending_count']}")
        print(f"   Created: {camp['created_at']}")
        print()


def test_content():
    """Test email content validation"""
    print_header("Content Validation Test")
    
    print("Enter email content to test:")
    print()
    
    subject = input("Subject: ").strip()
    if not subject:
        subject = "Test Email"
    
    print("Body (HTML, press Enter twice to finish):")
    body_lines = []
    while True:
        line = input()
        if not line:
            break
        body_lines.append(line)
    
    body = "\n".join(body_lines) if body_lines else "<p>Test body</p>"
    
    print()
    print("Validating content...")
    is_valid, warnings = validate_email_content(subject, body)
    
    print()
    if is_valid:
        print("✅ Content validation passed!")
    else:
        print("❌ Content validation failed!")
    
    if warnings:
        print("\n⚠️  Warnings:")
        for warning in warnings:
            print(f"   - {warning}")
    else:
        print("\n✨ No warnings - content looks great!")
    
    print()


def export_suppression_list():
    """Export suppression list backup"""
    print_header("Export Suppression List")
    
    suppression = get_suppression_manager()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"suppression_backup_{timestamp}.csv"
    
    success = suppression.export_suppression_list(filename)
    
    if success:
        print(f"✅ Exported to: {filename}")
    else:
        print(f"❌ Export failed")
    
    print()


def main_menu():
    """Show main menu and handle user input"""
    while True:
        print_header("Email Deliverability Setup & Status")
        
        print("1. Show Current Status")
        print("2. Setup Domain Verification (start warm-up)")
        print("3. View Campaigns")
        print("4. Test Email Content")
        print("5. Export Suppression List")
        print("6. Exit")
        print()
        
        choice = input("Select option (1-6): ").strip()
        
        if choice == '1':
            show_current_status()
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            setup_domain_verification()
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            show_campaigns()
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            test_content()
            input("\nPress Enter to continue...")
        
        elif choice == '5':
            export_suppression_list()
            input("\nPress Enter to continue...")
        
        elif choice == '6':
            print("\nGoodbye! 👋")
            sys.exit(0)
        
        else:
            print("\n❌ Invalid option. Please select 1-6.")
            input("Press Enter to continue...")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye! 👋")
        sys.exit(0)
