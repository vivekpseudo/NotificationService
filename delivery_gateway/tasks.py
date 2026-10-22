from celery import shared_task
from celery.utils.log import get_task_logger
from .services import ChannelFactory
from .models import NotificationLog

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=5)
def send_message(self, user_id, channel, destination, content):
    """Deliver a message, redact webhook secrets from logs, and retry transient failures."""
    logger.info("Attempting delivery via %s", channel)
    service = ChannelFactory.get_service(channel)
    safe_destination = "[redacted webhook]" if channel == "teams" else (destination or "")

    if not service:
        logger.error("Unsupported notification channel: %s", channel)
        NotificationLog.objects.create(
            user_id=user_id,
            channel=channel,
            destination=safe_destination,
            content=content,
            status="failed",
            error_message="Unsupported channel",
        )
        return False

    error_message = "Delivery failed at provider"
    try:
        success = service.send(destination, content)
        if success:
            NotificationLog.objects.create(
                user_id=user_id,
                channel=channel,
                destination=safe_destination,
                content=content,
                status="sent",
            )
            return True
    except Exception as exc:
        error_message = type(exc).__name__
        logger.warning("Notification delivery failed on %s (%s)", channel, error_message)

    NotificationLog.objects.create(
        user_id=user_id,
        channel=channel,
        destination=safe_destination,
        content=content,
        status="failed",
        error_message=error_message,
    )
    # Bounded exponential retry; provider adapters enforce their own request timeouts.
    raise self.retry(
        exc=RuntimeError(error_message),
        countdown=min(2 ** (self.request.retries + 1), 60),
    )
