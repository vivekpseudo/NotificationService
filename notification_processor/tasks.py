from celery import shared_task
from celery.utils.log import get_task_logger
from user_preferences.services import check_user_preference
from traffic_control.utils import RateLimiter
# from delivery_gateway.tasks import send_message # We will implement this next

logger = get_task_logger(__name__)

@shared_task(bind=True)
def process_event(self, event_data):
    """
    Acts as the Notification Generator.
    Transforms raw event data into a formatted notification payload.
    """
    print(f"DEBUG: Processing event: {event_data.get('event_type')}")
    logger.info(f"Processing event: {event_data.get('event_type')} for user {event_data.get('user_id')}")
    
    # 1. Generate Notification Content
    # In a real system, this might involve template rendering based on event_type
    payload = event_data.get('payload') or {}
    notification_content = str(payload.get('message') or f"New event: {event_data.get('event_type')}")
    app_url = payload.get('app_url')
    if app_url:
        notification_content += f"\\nOpen OKR: {app_url}"
    
    # 2. Forward to Router
    # We could call route_notification directly or as a separate task for more granularity
    route_notification.delay(event_data['user_id'], notification_content, event_data.get('timestamp'))

@shared_task
def route_notification(user_id, content, timestamp):
    """
    Acts as the Notification Router.
    Checks preferences and rate limits, then dispatches to delivery channels.
    """
    print(f"DEBUG: Routing notification for user {user_id}")
    logger.info(f"Routing notification for user {user_id}")
    
    # Define available channels - in reality this might be dynamic or based on event type
    available_channels = ['email', 'slack', 'in_app', 'teams']
    
    rate_limiter = RateLimiter(limit=5, window=60)
    
    for channel in available_channels:
        # 1. Check User Preferences
        is_enabled, destination = check_user_preference(user_id, channel)
        
        if not is_enabled:
            logger.debug(f"Channel {channel} disabled for user {user_id}. Skipping.")
            continue
            
        # 2. Check Rate Limits
        if not rate_limiter.is_allowed(user_id, channel):
            logger.warning(f"Rate limit exceeded for user {user_id} on channel {channel}. Dropping.")
            # In a real system, maybe we queue it for later or aggregate?
            continue
            
        # 3. Dispatch to Delivery Service
        # We need to import the task dynamically or use send_task if circular imports are an issue
        # trying to keep things decoupled
        from celery import current_app
        task_name = 'delivery_gateway.tasks.send_message'
        
        if current_app.conf.task_always_eager:
            current_app.tasks[task_name].delay(user_id, channel, destination, content)
        else:
            current_app.send_task(task_name, args=[user_id, channel, destination, content])

        logger.info(f"Dispatched to {channel} for user {user_id}")
