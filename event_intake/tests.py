import hashlib
import hmac
import json
import os
import time
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from .views import verify_okr_signature


class OkrSignatureTests(SimpleTestCase):
    secret = "test-shared-secret-that-is-long-enough-for-ci"

    def make_request(self, timestamp=None, signature_override=None):
        body = json.dumps({
            "event_type": "okr.weekly_checkin_reminder",
            "user_id": "user-123",
            "source": "okr",
            "payload": {"message": "Time for a check-in."},
        }, separators=(",", ":"))
        issued_at = str(timestamp if timestamp is not None else int(time.time()))
        signature = hmac.new(
            self.secret.encode(),
            issued_at.encode("ascii") + b"." + body.encode(),
            hashlib.sha256,
        ).hexdigest()
        request = APIRequestFactory().post(
            "/api/events/",
            data=body,
            content_type="application/json",
            HTTP_X_OKR_TIMESTAMP=issued_at,
            HTTP_X_OKR_SIGNATURE=signature_override if signature_override is not None else signature,
        )
        return request

    @patch.dict(os.environ, {"OKR_NOTIFICATION_SHARED_SECRET": secret})
    def test_accepts_valid_signature(self):
        self.assertTrue(verify_okr_signature(self.make_request()))

    @patch.dict(os.environ, {"OKR_NOTIFICATION_SHARED_SECRET": secret})
    def test_rejects_tampered_signature(self):
        self.assertFalse(verify_okr_signature(self.make_request(signature_override="0" * 64)))

    @patch.dict(os.environ, {"OKR_NOTIFICATION_SHARED_SECRET": secret})
    def test_rejects_stale_timestamp(self):
        self.assertFalse(verify_okr_signature(self.make_request(timestamp=int(time.time()) - 301)))

    @patch.dict(os.environ, {"OKR_NOTIFICATION_SHARED_SECRET": ""})
    @override_settings(DEBUG=False)
    def test_rejects_unsigned_requests_without_configured_secret(self):
        self.assertFalse(verify_okr_signature(self.make_request()))
