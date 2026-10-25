import unittest

from fastapi import HTTPException
from starlette.requests import Request

from e2e.config.security import require_client_certificate


def make_request(headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [
                (name.lower().encode("ascii"), value.encode("ascii"))
                for name, value in headers.items()
            ],
        }
    )


class RequireClientCertificateTests(unittest.TestCase):
    def test_rejects_missing_certificate_headers(self):
        with self.assertRaises(HTTPException) as raised:
            require_client_certificate(make_request({}))

        self.assertEqual(raised.exception.status_code, 401)

    def test_rejects_unverified_certificate(self):
        request = make_request(
            {
                "x-client-verify": "FAILED",
                "x-client-subject": "CN=demo-api-client",
            }
        )

        with self.assertRaises(HTTPException) as raised:
            require_client_certificate(request)

        self.assertEqual(raised.exception.status_code, 401)

    def test_rejects_missing_certificate_subject(self):
        request = make_request({"x-client-verify": "SUCCESS"})

        with self.assertRaises(HTTPException) as raised:
            require_client_certificate(request)

        self.assertEqual(raised.exception.status_code, 401)

    def test_returns_subject_for_verified_certificate(self):
        request = make_request(
            {
                "x-client-verify": "SUCCESS",
                "x-client-subject": "CN=demo-api-client",
            }
        )

        self.assertEqual(
            require_client_certificate(request),
            "CN=demo-api-client",
        )


if __name__ == "__main__":
    unittest.main()
