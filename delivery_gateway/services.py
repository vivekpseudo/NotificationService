import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class BaseChannelService:
    def send(self, destination, content):
        raise NotImplementedError


class EmailService(BaseChannelService):
    def send(self, destination, content):
        # Replace with a transactional email provider before enabling email in production.
        logger.warning("Email delivery adapter is not configured")
        return False


class SlackService(BaseChannelService):
    def send(self, destination, content):
        token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not token:
            logger.error("Slack delivery skipped: SLACK_BOT_TOKEN is not configured")
            return False
        if not destination or not re.fullmatch(r"[A-Z0-9_-]{1,100}", destination, re.IGNORECASE):
            logger.error("Slack delivery rejected: destination must be a channel ID")
            return False
        payload = json.dumps({
            "channel": destination,
            "text": str(content)[:3000],
            "unfurl_links": False,
            "unfurl_media": False,
        }).encode("utf-8")
        request = Request(
            "https://slack.com/api/chat.postMessage",
            data=payload,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=8) as response:
                result = json.loads(response.read(65536).decode("utf-8"))
            if result.get("ok") is not True:
                logger.error("Slack delivery failed: %s", result.get("error", "provider rejected request"))
                return False
            return True
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            logger.error("Slack delivery failed (%s)", type(exc).__name__)
            return False


class InAppService(BaseChannelService):
    def send(self, destination, content):
        # Persist in-app notifications in a dedicated table before enabling this channel.
        logger.warning("In-app delivery adapter is not configured")
        return False


class TeamsService(BaseChannelService):
    ALLOWED_SUFFIXES = (".webhook.office.com", ".logic.azure.com", ".powerplatform.com")
    ALLOWED_HOSTS = ("webhook.office.com", "logic.azure.com", "powerplatform.com")

    @classmethod
    def allowed_url(cls, value):
        try:
            parsed = urlparse(value)
            host = (parsed.hostname or "").lower()
            allowed = host in cls.ALLOWED_HOSTS or any(host.endswith(suffix) for suffix in cls.ALLOWED_SUFFIXES)
            return parsed.scheme == "https" and allowed and not parsed.username and not parsed.password and not parsed.port
        except (TypeError, ValueError):
            return False

    def send(self, destination, content):
        if not self.allowed_url(destination):
            logger.error("Teams delivery rejected: destination is not an approved Microsoft webhook host")
            return False
        payload = json.dumps({"text": str(content)[:3000]}).encode("utf-8")
        request = Request(
            destination,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # Redirects are not followed: a webhook cannot redirect this server to another host.
            with urlopen(request, timeout=8) as response:
                return 200 <= response.status < 300
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            logger.error("Teams delivery failed (%s)", type(exc).__name__)
            return False


class ChannelFactory:
    @staticmethod
    def get_service(channel):
        return {
            "email": EmailService,
            "slack": SlackService,
            "in_app": InAppService,
            "teams": TeamsService,
        }.get(channel, lambda: None)()
