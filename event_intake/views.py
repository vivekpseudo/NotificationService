import hashlib
import hmac
import json
import logging
import os
import time

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .serializers import EventSerializer
from .tasks import publish_event

logger = logging.getLogger(__name__)


def verify_okr_signature(request):
    secret = os.environ.get("OKR_NOTIFICATION_SHARED_SECRET", "")
    if not secret:
        # Never silently expose an unauthenticated event intake in production.
        return bool(settings.DEBUG)
    timestamp = request.headers.get("X-OKR-Timestamp", "")
    signature = request.headers.get("X-OKR-Signature", "")
    try:
        issued_at = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(int(time.time()) - issued_at) > 300:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("ascii") + b"." + request.body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


class EventIntakeView(APIView):
    # HMAC is the authentication mechanism for this service-to-service endpoint.
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not verify_okr_signature(request):
            logger.warning("Rejected event intake: missing or invalid service signature")
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = EventSerializer(data=request.data)
        if serializer.is_valid():
            event_data = dict(serializer.validated_data)
            if event_data.get('timestamp') is not None:
                event_data['timestamp'] = event_data['timestamp'].isoformat()
            publish_event.delay(event_data)
            logger.info("Event received and queued: %s", event_data["event_type"])
            return Response({"status": "accepted", "message": "Event queued for processing"}, status=status.HTTP_202_ACCEPTED)
        logger.warning("Invalid event payload: %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
