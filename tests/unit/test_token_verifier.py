"""Unit tests for token_verifier.py using real JWT validation.

This test suite provides comprehensive coverage of the JWKSTokenVerifier class functionality
using REAL JWT validation instead of mocking. This ensures we catch actual security bugs
in the JWT validation logic.

Test Coverage:
1. Initialization and Configuration
   - Proper initialization with JWKS endpoint, issuer, and audience
   - PyJWKClient initialization with correct endpoint

2. Token Verification (verify_token method)
   - Successful token verification with valid JWT
   - Handling of missing signing keys from JWKS
   - Handling of JWT validation failures
   - Exception handling during verification process
   - Edge cases: missing audience, missing expiration time
   - Logging behavior (debug and warning messages)

3. JWT Validation (_decode_and_validate_jwt method)
   - Successful JWT decoding and validation
   - Missing required claims (exp, iat, iss, aud)
   - Invalid signature handling
   - Expired token handling
   - Invalid issuer handling
   - Invalid audience handling
   - Generic exception handling
   - Verification parameter validation (algorithms, issuer, audience, options, leeway)

4. Error Handling and Logging
   - Warning messages for various failure scenarios
   - Debug logging for successful operations
   - Exception handling and graceful degradation

5. Edge Cases and Boundary Conditions
   - Missing optional fields in JWT payload
   - Various JWT validation error types
   - PyJWKClient integration with real JWKS

The tests use REAL cryptographic operations to ensure security validation works correctly.
"""

import http.server
import json
import socketserver
import threading
import time
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp.server.auth.provider import AccessToken

from semgrep_mcp.token_verifier import JWKSTokenVerifier


class MockJWKSServer:
    """Mock JWKS server for testing purposes."""

    def __init__(self, port=0):
        self.port = port
        self.jwks_data = {}
        self.server = None
        self.thread = None

    def start(self):
        """Start the mock JWKS server."""
        handler = self._create_handler()
        self.server = socketserver.TCPServer(("", self.port), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the mock JWKS server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def _create_handler(self):
        server = self

        class JWKSHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/.well-known/jwks.json":
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(server.jwks_data).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                # Suppress logging for tests
                pass

        return JWKSHandler


class TestJWKSTokenVerifier:
    """Test cases for JWKSTokenVerifier class using real JWT validation."""

    @classmethod
    def setup_class(cls):
        """Set up test fixtures for the entire test class."""
        # Generate RSA key pair for testing
        cls.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        cls.public_key = cls.private_key.public_key()

        # Export public key in JWK format
        cls.public_numbers = cls.public_key.public_numbers()
        cls.jwk = {
            "kty": "RSA",
            "kid": "test-key-1",
            "use": "sig",
            "alg": "RS256",
            "n": jwt.utils.base64url_encode(cls.public_numbers.n.to_bytes(256, 'big')).decode(),
            "e": jwt.utils.base64url_encode(cls.public_numbers.e.to_bytes(3, 'big')).decode()
        }

        # Start mock JWKS server
        cls.jwks_server = MockJWKSServer()
        cls.jwks_server.jwks_data = {"keys": [cls.jwk]}
        cls.jwks_server.start()

        # Wait a moment for server to start
        time.sleep(0.1)

    @classmethod
    def teardown_class(cls):
        """Clean up test fixtures."""
        if cls.jwks_server:
            cls.jwks_server.stop()

    def test_init(self):
        """Test JWKSTokenVerifier initialization."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        assert verifier.jwks_endpoint == jwks_endpoint
        assert verifier.issuer == issuer
        assert verifier.audience == audience
        assert hasattr(verifier._jwk_client, 'uri')
        assert verifier._jwk_client.uri == jwks_endpoint

    def _create_test_jwt(self, payload, expires_in_hours=1):
        """Create a real JWT token for testing."""
        # Add standard claims if not present
        now = int(time.time())
        if 'iat' not in payload:
            payload['iat'] = now
        if 'exp' not in payload:
            payload['exp'] = now + (expires_in_hours * 3600)
        if 'iss' not in payload:
            payload['iss'] = "https://example.com"
        if 'aud' not in payload:
            payload['aud'] = "test-client"
        if 'sub' not in payload:
            payload['sub'] = "test-user"

        # Create JWT with real RSA signing
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key-1"}
        )
        return token

    @pytest.mark.asyncio
    async def test_verify_token_success(self):
        """Test successful token verification with real JWT."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a valid JWT
        payload = {
            "sub": "user123",
            "email": "user@example.com"
        }
        token = self._create_test_jwt(payload)

        # Verify the token
        result = await verifier.verify_token(token)

        assert result is not None
        assert isinstance(result, AccessToken)
        assert result.token == token
        assert result.client_id == "test-client"
        assert result.scopes == ["openid", "profile", "email"]
        assert result.expires_at == payload["exp"]

    @pytest.mark.asyncio
    async def test_verify_token_no_signing_key(self):
        """Test token verification when no signing key is found."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT with a non-existent key ID
        payload = {"sub": "user123"}
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "non-existent-key"}
        )

        result = await verifier.verify_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_expired_token(self):
        """Test token verification with expired token."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create an expired JWT
        payload = {
            "sub": "user123",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 7200,  # Issued 2 hours ago
        }
        token = self._create_test_jwt(payload, expires_in_hours=-1)

        result = await verifier.verify_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_invalid_issuer(self):
        """Test token verification with invalid issuer."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT with wrong issuer
        payload = {
            "sub": "user123",
            "iss": "https://malicious.com"
        }
        token = self._create_test_jwt(payload)

        result = await verifier.verify_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_invalid_audience(self):
        """Test token verification with invalid audience."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT with wrong audience
        payload = {
            "sub": "user123",
            "aud": "wrong-client"
        }
        token = self._create_test_jwt(payload)

        result = await verifier.verify_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_missing_required_claims(self):
        """Test token verification with missing required claims."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT missing required claims
        payload = {
            "sub": "user123"
            # Missing exp, iat, iss, aud
        }
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key-1"}
        )

        result = await verifier.verify_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_invalid_signature(self):
        """Test token verification with invalid signature."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT with valid payload but tamper with it
        payload = {"sub": "user123"}
        token = self._create_test_jwt(payload)

        # Tamper with the token by changing a character
        tampered_token = token[:-1] + "X"

        result = await verifier.verify_token(tampered_token)
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_with_unknown_audience(self):
        """Test token verification when audience is not in payload."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT without 'aud' field but with other required claims
        payload = {
            "sub": "user123",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "iss": "https://example.com"
        }
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key-1"}
        )

        result = await verifier.verify_token(token)
        # The JWT validation correctly rejects tokens missing required claims
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_with_no_expires_at(self):
        """Test token verification when exp field is not in payload."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT without 'exp' field but with other required claims
        payload = {
            "aud": "test-client",
            "iat": int(time.time()),
            "iss": "https://example.com",
            "sub": "user123"
        }
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key-1"}
        )

        result = await verifier.verify_token(token)
        # The JWT validation correctly rejects tokens missing required claims
        assert result is None

    def test_decode_and_validate_jwt_success(self):
        """Test successful JWT decoding and validation with real JWT."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a valid JWT
        payload = {
            "aud": "test-client",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "iss": "https://example.com",
            "sub": "user123"
        }
        token = self._create_test_jwt(payload)

        # Test the private method directly
        result = verifier._decode_and_validate_jwt(token, self.public_key)

        assert result is not None
        assert result["sub"] == "user123"
        assert result["aud"] == "test-client"
        assert result["iss"] == "https://example.com"

    def test_decode_and_validate_jwt_missing_required_claims(self):
        """Test JWT validation with missing required claims."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT missing required claims
        payload = {"sub": "user123"}
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key-1"}
        )

        result = verifier._decode_and_validate_jwt(token, self.public_key)
        assert result is None

    def test_decode_and_validate_jwt_invalid_signature(self):
        """Test JWT validation with invalid signature."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT with valid payload but tamper with it
        payload = {"sub": "user123"}
        token = self._create_test_jwt(payload)
        tampered_token = token[:-1] + "X"

        result = verifier._decode_and_validate_jwt(tampered_token, self.public_key)
        assert result is None

    def test_decode_and_validate_jwt_expired_token(self):
        """Test JWT validation with expired token."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create an expired JWT
        payload = {
            "aud": "test-client",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 7200,  # Issued 2 hours ago
            "iss": "https://example.com",
            "sub": "user123"
        }
        token = self._create_test_jwt(payload, expires_in_hours=-1)

        result = verifier._decode_and_validate_jwt(token, self.public_key)
        assert result is None

    def test_decode_and_validate_jwt_invalid_issuer(self):
        """Test JWT validation with invalid issuer."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT with wrong issuer
        payload = {
            "aud": "test-client",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "iss": "https://malicious.com",
            "sub": "user123"
        }
        token = self._create_test_jwt(payload)

        result = verifier._decode_and_validate_jwt(token, self.public_key)
        assert result is None

    def test_decode_and_validate_jwt_invalid_audience(self):
        """Test JWT validation with invalid audience."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a JWT with wrong audience
        payload = {
            "aud": "wrong-client",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "iss": "https://example.com",
            "sub": "user123"
        }
        token = self._create_test_jwt(payload)

        result = verifier._decode_and_validate_jwt(token, self.public_key)
        assert result is None

    def test_decode_and_validate_jwt_verification_parameters(self):
        """Test that JWT decode is called with correct verification parameters."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a valid JWT
        payload = {
            "aud": "test-client",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "iss": "https://example.com",
            "sub": "user123"
        }
        token = self._create_test_jwt(payload)

        # Test with a mock to verify parameters, but use real JWT
        with patch('jwt.decode') as mock_decode:
            mock_decode.return_value = payload

            verifier._decode_and_validate_jwt(token, self.public_key)

            # Verify JWT decode was called with correct parameters
            mock_decode.assert_called_once_with(
                token,
                self.public_key,
                algorithms=["RS256"],
                issuer=issuer,
                audience=audience,
                options={"require": ["exp", "iat", "iss", "aud"]},
                leeway=10
            )

    @pytest.mark.asyncio
    async def test_verify_token_logging(self):
        """Test that appropriate logging occurs during token verification."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create a valid JWT
        payload = {"sub": "user123"}
        token = self._create_test_jwt(payload)

        with patch('semgrep_mcp.token_verifier.logger') as mock_logger:
            await verifier.verify_token(token)

            # Verify debug logging for token and payload
            mock_logger.debug.assert_any_call(f"JWT token: {token}")
            # Note: We can't easily test the payload logging without mocking the JWT decode

    @pytest.mark.asyncio
    async def test_verify_token_warning_logging_on_failure(self):
        """Test that warning logging occurs when token verification fails."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        with patch('semgrep_mcp.token_verifier.logger') as mock_logger:
            # Use a token with non-existent key ID to trigger the warning
            payload = {"sub": "user123"}
            token = jwt.encode(
                payload,
                self.private_key,
                algorithm="RS256",
                headers={"kid": "non-existent-key"}
            )

            await verifier.verify_token(token)

            # Verify warning logging for missing signing key
            mock_logger.warning.assert_called_with(
                "JWT validation failed: Unable to find a signing key that matches: "
                "\"non-existent-key\""
            )

    def test_decode_and_validate_jwt_warning_logging_on_error(self):
        """Test that warning logging occurs when JWT validation fails."""
        jwks_endpoint = f"http://localhost:{self.jwks_server.port}/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        # Create an expired JWT to trigger validation error
        payload = {
            "aud": "test-client",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 7200,  # Issued 2 hours ago
            "iss": "https://example.com",
            "sub": "user123"
        }
        token = self._create_test_jwt(payload, expires_in_hours=-1)

        with patch('semgrep_mcp.token_verifier.logger') as mock_logger:
            verifier._decode_and_validate_jwt(token, self.public_key)

            # Verify warning logging for JWT validation error
            mock_logger.warning.assert_called()
            # The exact message may vary, so just check that warning was called
