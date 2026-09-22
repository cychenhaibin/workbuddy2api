"""安全响应头回归测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from server.main import app  # noqa: E402


class SecurityHeadersTest(unittest.TestCase):
    def test_allows_only_the_configured_iframe_parent(self) -> None:
        response = TestClient(app).get('/api/healthz')

        self.assertNotIn('x-frame-options', response.headers)
        self.assertIn(
            "frame-ancestors 'self' https://fluxa.camila.qzz.io",
            response.headers['content-security-policy'],
        )
        self.assertNotIn(
            "frame-ancestors 'none'",
            response.headers['content-security-policy'],
        )


if __name__ == '__main__':
    unittest.main()
