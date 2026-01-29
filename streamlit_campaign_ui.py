"""
Streamlit Campaign Manager UI Component

Provides schedule visualization and campaign control interface.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import config
from email_queue import get_queue_manager, JobStatus
from schedule_calculator import get_schedule_calculator
from engagement_scorer import get_engagement_scorer
from campaign_validator import get_campaign_validator
from sending_limits_tracker import get_limits_tracker
from suppression_list_manager import get_suppression_manager


def show_limits_dashboard():
    '''Display current sending limits and usage'''
    st.subheader('📊 Sending Limits Dashboard')
    
    limits_tracker = get_limits_tracker()
    limits = limits_tracker.get_limits_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            'Daily Limit',
            limits['daily_limit'],
            delta=f"Day {limits['domain_age_days']}/{config.EMAIL_WARMUP_DAYS}"
        )
    
    with col2:
        remaining = limits['daily_limit'] - limits['sent_today']
        st.metric(
            'Remaining Today',
            remaining,
            delta=f"-{limits['sent_today']} sent"
        )
    
    with col3:
        st.metric(
            'Hourly Limit',
            config.EMAIL_MAX_HOURLY_VOLUME
        )
    
    with col4:
        suppression_manager = get_suppression_manager()
        stats = suppression_manager.get_suppression_stats()
        st.metric(
            'Suppression List',
            stats['total']
        )
    
    # Progress bar
    if limits['daily_limit'] > 0:
        progress = limits['sent_today'] / limits['daily_limit']
        st.progress(progress, text=f"Today's usage: {progress*100:.1f}%")


def show_schedule_preview(
    contacts: List[Dict],
    start_date: datetime = None,
    respect_warmup: bool = True
):
    '''Display schedule preview table'''
    st.subheader('📅 Schedule Preview')
    
    calculator = get_schedule_calculator()
    
    # Calculate schedule
    schedule = calculator.calculate_schedule(
        total_emails=len(contacts),
        start_date=start_date,
        respect_warmup=respect_warmup
    )
    
    # Format as DataFrame
    df = calculator.format_schedule_table(schedule)
    
    # Display
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )
    
    # Show summary
    summary = calculator.estimate_completion(schedule)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric('Total Emails', summary['total_emails'])
    with col2:
        st.metric('Days Required', summary['days_required'])
    with col3:
        completion_date = summary['estimated_completion']
        st.metric('Completion', completion_date.strftime('%Y-%m-%d'))
    
    # Warnings
    if summary['warnings']:
        with st.expander('⚠️ Warnings', expanded=False):
            for warning in summary['warnings']:
                st.warning(warning)


def show_engagement_filter(contacts: List[Dict], engagement_data: Dict = None):
    '''Show engagement tier selector'''
    st.subheader('🎯 Engagement Filtering')
    
    scorer = get_engagement_scorer()
    
    # Score contacts if engagement data provided
    if engagement_data:
        contacts = scorer.score_contacts(contacts, engagement_data)
        summary = scorer.get_engagement_summary(contacts)
        
        # Show distribution
        st.write('**Engagement Distribution:**')
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric('Tier 1 (Hot)', summary['tier_1'])
        with col2:
            st.metric('Tier 2 (Warm)', summary['tier_2'])
        with col3:
            st.metric('Tier 3 (Cold)', summary['tier_3'])
        with col4:
            st.metric('Tier 4 (Inactive)', summary['tier_4'])
    
    # Tier selector
    selected_tiers = st.multiselect(
        'Include engagement tiers',
        options=[1, 2, 3, 4],
        default=[1, 2, 3, 4],
        help='Tier 1 = Most engaged (last 30 days), Tier 4 = Least engaged (180+ days)'
    )
    
    # Filter contacts
    if selected_tiers and engagement_data:
        filtered = scorer.filter_by_engagement(contacts, selected_tiers)
        st.info(f'Selected {len(filtered)} of {len(contacts)} contacts')
        return filtered
    
    return contacts


def show_campaign_mode_selector():
    '''Show campaign mode selection'''
    st.subheader('🚀 Campaign Mode')
    
    mode = st.radio(
        'Select sending mode',
        options=['Auto Schedule', 'Bucket Mode', 'Custom Schedule'],
        help='''
        - Auto Schedule: Respects warm-up and daily limits (recommended)
        - Bucket Mode: Same-day sending in chunks (use after warm-up only!)
        - Custom Schedule: Manually specify dates and counts
        '''
    )
    
    mode_config = {}
    
    if mode == 'Bucket Mode':
        st.warning('⚠️ Use ONLY after warm-up period complete!')
        col1, col2 = st.columns(2)
        with col1:
            mode_config['num_buckets'] = st.slider(
                'Number of buckets',
                min_value=2,
                max_value=10,
                value=5
            )
        with col2:
            mode_config['delay_hours'] = st.slider(
                'Delay between buckets (hours)',
                min_value=0.5,
                max_value=4.0,
                value=1.0,
                step=0.5
            )
    
    elif mode == 'Custom Schedule':
        st.info('📝 Define your own schedule by date')
        
        # Simple custom schedule builder
        num_days = st.number_input(
            'Number of days',
            min_value=1,
            max_value=30,
            value=7
        )
        
        schedule_items = []
        for i in range(num_days):
            col1, col2 = st.columns(2)
            with col1:
                date = st.date_input(
                    f'Day {i+1} date',
                    value=datetime.now().date() + timedelta(days=i),
                    key=f'custom_date_{i}'
                )
            with col2:
                count = st.number_input(
                    f'Day {i+1} count',
                    min_value=0,
                    max_value=5000,
                    value=100,
                    key=f'custom_count_{i}'
                )
            
            if count > 0:
                schedule_items.append({
                    'date': date.isoformat(),
                    'count': count
                })
        
        mode_config['custom_schedule'] = schedule_items
    
    return mode, mode_config


def show_preflight_checklist(
    sender_email: str,
    subject: str,
    body: str,
    contacts: List[Dict]
):
    '''Display pre-flight validation checklist'''
    st.subheader('✅ Pre-Flight Checklist')
    
    validator = get_campaign_validator()
    
    # Run validation
    is_valid, errors, warnings = validator.validate_campaign(
        sender_email=sender_email,
        subject=subject,
        body=body,
        contacts=contacts
    )
    
    # Show status
    if is_valid:
        st.success('✅ All checks passed! Campaign ready to send.')
    else:
        st.error('❌ Campaign has blocking errors. Fix before sending.')
    
    # Show errors
    if errors:
        with st.expander('❌ Errors (must fix)', expanded=True):
            for error in errors:
                st.error(error)
    
    # Show warnings
    if warnings:
        with st.expander('⚠️ Warnings (recommend fixing)', expanded=False):
            for warning in warnings:
                st.warning(warning)
    
    return is_valid


def show_campaign_creator(
    sender_email: str,
    sender_name: str,
    subject: str,
    body: str,
    contacts: List[Dict],
    attachments: List[str] = None
):
    '''Complete campaign creation interface'''
    st.title('📧 Create Email Campaign')
    
    # Limits dashboard
    show_limits_dashboard()
    
    st.divider()
    
    # Engagement filtering
    engagement_data = st.session_state.get('engagement_data', None)
    filtered_contacts = show_engagement_filter(contacts, engagement_data)
    
    st.divider()
    
    # Campaign mode
    mode, mode_config = show_campaign_mode_selector()
    
    st.divider()
    
    # Schedule preview (for auto mode)
    if mode == 'Auto Schedule':
        show_schedule_preview(
            filtered_contacts,
            respect_warmup=True
        )
    elif mode == 'Bucket Mode':
        st.info(
            f"📦 Will send {len(filtered_contacts)} emails in "
            f"{mode_config.get('num_buckets', 5)} buckets over "
            f"{mode_config.get('delay_hours', 1.0) * mode_config.get('num_buckets', 5):.1f} hours"
        )
    elif mode == 'Custom Schedule':
        total_scheduled = sum(item['count'] for item in mode_config.get('custom_schedule', []))
        if total_scheduled != len(filtered_contacts):
            st.warning(
                f"⚠️ Schedule total ({total_scheduled}) doesn't match "
                f"contact count ({len(filtered_contacts)})"
            )
    
    st.divider()
    
    # Pre-flight checklist
    is_valid = show_preflight_checklist(
        sender_email=sender_email,
        subject=subject,
        body=body,
        contacts=filtered_contacts
    )
    
    st.divider()
    
    # Campaign name input
    campaign_name = st.text_input(
        'Campaign Name',
        value=f"Campaign {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    # Create button
    if st.button('🚀 Create Campaign', type='primary', disabled=not is_valid):
        queue_manager = get_queue_manager()
        
        try:
            # Create campaign based on mode
            if mode == 'Auto Schedule':
                campaign_id = queue_manager.create_campaign(
                    name=campaign_name,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    subject=subject,
                    body=body,
                    contacts=filtered_contacts,
                    attachments=attachments
                )
            
            elif mode == 'Bucket Mode':
                campaign_id = queue_manager.create_campaign_with_bucket_mode(
                    name=campaign_name,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    subject=subject,
                    body=body,
                    contacts=filtered_contacts,
                    num_buckets=mode_config['num_buckets'],
                    delay_between_buckets_hours=mode_config['delay_hours'],
                    attachments=attachments
                )
            
            elif mode == 'Custom Schedule':
                campaign_id = queue_manager.create_campaign_with_custom_schedule(
                    name=campaign_name,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    subject=subject,
                    body=body,
                    contacts=filtered_contacts,
                    custom_schedule=mode_config['custom_schedule'],
                    attachments=attachments
                )
            
            st.success(f'✅ Campaign created! ID: {campaign_id}')
            st.balloons()
            
            # Show next steps
            st.info(
                '**Next Steps:**\n'
                '1. Start queue processor: python queue_processor.py\n'
                '2. Monitor campaign in Campaign Dashboard\n'
                '3. Emails will send automatically according to schedule'
            )
        
        except Exception as e:
            st.error(f'❌ Error creating campaign: {e}')


def show_campaign_dashboard():
    '''Show all campaigns with status'''
    st.title('📊 Campaign Dashboard')
    
    queue_manager = get_queue_manager()
    campaigns = queue_manager.get_all_campaigns()
    
    if not campaigns:
        st.info('No campaigns yet. Create your first campaign!')
        return
    
    # Create DataFrame
    df = pd.DataFrame(campaigns)
    
    # Format columns
    df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    df['progress'] = df['progress_pct'].round(1).astype(str) + '%'
    
    # Display
    st.dataframe(
        df[[
            'name', 'created_at', 'status',
            'total_contacts', 'sent_count', 'failed_count',
            'pending_count', 'progress'
        ]],
        use_container_width=True,
        hide_index=True
    )
    
    # Campaign controls
    st.subheader('Campaign Controls')
    
    campaign_ids = [c['id'] for c in campaigns]
    selected_campaign = st.selectbox('Select campaign', campaign_ids)
    
    if selected_campaign:
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button('⏸️ Pause Campaign'):
                if queue_manager.pause_campaign(selected_campaign):
                    st.success('Campaign paused')
                    st.rerun()
        
        with col2:
            if st.button('▶️ Resume Campaign'):
                if queue_manager.resume_campaign(selected_campaign):
                    st.success('Campaign resumed')
                    st.rerun()
