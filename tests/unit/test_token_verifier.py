"""Unit tests for token_verifier.py.

This test suite provides comprehensive coverage of the JWKSTokenVerifier class functionality:

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
   - PyJWKClient integration and mocking

The tests use comprehensive mocking to isolate the unit under test and verify
all code paths and error conditions are properly handled.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime, timedelta
import jwt
from jwt import PyJWKClient

from semgrep_mcp.token_verifier import JWKSTokenVerifier
from mcp.server.auth.provider import AccessToken


class TestJWKSTokenVerifier:
    """Test cases for JWKSTokenVerifier class."""

    def test_init(self):
        """Test JWKSTokenVerifier initialization."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"

        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)

        assert verifier.jwks_endpoint == jwks_endpoint
        assert verifier.issuer == issuer
        assert verifier.audience == audience
        assert isinstance(verifier._jwk_client, PyJWKClient)
        assert verifier._jwk_client.uri == jwks_endpoint

    @pytest.mark.asyncio
    async def test_verify_token_success(self):
        """Test successful token verification."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT payload
        mock_payload = {
            "aud": "test-client",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "iss": "https://example.com",
            "sub": "user123"
        }
        
        # Mock signing key
        mock_signing_key = MagicMock()
        mock_signing_key.key = "mock-public-key"
        
        with patch.object(verifier._jwk_client, 'get_signing_key_from_jwt', return_value=mock_signing_key):
            with patch.object(verifier, '_decode_and_validate_jwt', return_value=mock_payload):
                result = await verifier.verify_token("mock.jwt.token")
                
                assert result is not None
                assert isinstance(result, AccessToken)
                assert result.token == "mock.jwt.token"
                assert result.client_id == "test-client"
                assert result.scopes == ["openid", "profile", "email"]
                assert result.expires_at == mock_payload["exp"]

    @pytest.mark.asyncio
    async def test_verify_token_no_signing_key(self):
        """Test token verification when no signing key is found."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        with patch.object(verifier._jwk_client, 'get_signing_key_from_jwt', return_value=None):
            result = await verifier.verify_token("mock.jwt.token")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_validation_failure(self):
        """Test token verification when JWT validation fails."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock signing key
        mock_signing_key = MagicMock()
        mock_signing_key.key = "mock-public-key"
        
        with patch.object(verifier._jwk_client, 'get_signing_key_from_jwt', return_value=mock_signing_key):
            with patch.object(verifier, '_decode_and_validate_jwt', return_value=None):
                result = await verifier.verify_token("mock.jwt.token")
                
                assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_exception_handling(self):
        """Test token verification exception handling."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock signing key
        mock_signing_key = MagicMock()
        mock_signing_key.key = "mock-public-key"
        
        with patch.object(verifier._jwk_client, 'get_signing_key_from_jwt', side_effect=Exception("JWKS error")):
            result = await verifier.verify_token("mock.jwt.token")
            
            assert result is None

    def test_decode_and_validate_jwt_success(self):
        """Test successful JWT decoding and validation."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Create a valid JWT payload
        payload = {
            "aud": "test-client",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "iss": "https://example.com",
            "sub": "user123"
        }
        
        # Mock the JWT decode function
        with patch('jwt.decode', return_value=payload):
            result = verifier._decode_and_validate_jwt("mock.jwt.token", "mock-public-key")
            
            assert result == payload

    def test_decode_and_validate_jwt_missing_required_claims(self):
        """Test JWT validation with missing required claims."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT decode to raise an exception for missing claims
        with patch('jwt.decode', side_effect=jwt.MissingRequiredClaimError("Missing required claim: exp")):
            result = verifier._decode_and_validate_jwt("mock.jwt.token", "mock-public-key")
            
            assert result is None

    def test_decode_and_validate_jwt_invalid_signature(self):
        """Test JWT validation with invalid signature."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT decode to raise an exception for invalid signature
        with patch('jwt.decode', side_effect=jwt.InvalidSignatureError("Invalid signature")):
            result = verifier._decode_and_validate_jwt("mock.jwt.token", "mock-public-key")
            
            assert result is None

    def test_decode_and_validate_jwt_expired_token(self):
        """Test JWT validation with expired token."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT decode to raise an exception for expired token
        with patch('jwt.decode', side_effect=jwt.ExpiredSignatureError("Token has expired")):
            result = verifier._decode_and_validate_jwt("mock.jwt.token", "mock-public-key")
            
            assert result is None

    def test_decode_and_validate_jwt_invalid_issuer(self):
        """Test JWT validation with invalid issuer."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT decode to raise an exception for invalid issuer
        with patch('jwt.decode', side_effect=jwt.InvalidIssuerError("Invalid issuer")):
            result = verifier._decode_and_validate_jwt("mock.jwt.token", "mock-public-key")
            
            assert result is None

    def test_decode_and_validate_jwt_invalid_audience(self):
        """Test JWT validation with invalid audience."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT decode to raise an exception for invalid audience
        with patch('jwt.decode', side_effect=jwt.InvalidAudienceError("Invalid audience")):
            result = verifier._decode_and_validate_jwt("mock.jwt.token", "mock-public-key")
            
            assert result is None

    def test_decode_and_validate_jwt_generic_exception(self):
        """Test JWT validation with generic exception."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT decode to raise a generic exception
        with patch('jwt.decode', side_effect=Exception("Generic JWT error")):
            result = verifier._decode_and_validate_jwt("mock.jwt.token", "mock-public-key")
            
            assert result is None

    def test_decode_and_validate_jwt_verification_parameters(self):
        """Test that JWT decode is called with correct verification parameters."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT decode to capture call parameters
        with patch('jwt.decode') as mock_decode:
            mock_decode.return_value = {"test": "payload"}
            
            verifier._decode_and_validate_jwt("mock.jwt.token", "mock-public-key")
            
            # Verify JWT decode was called with correct parameters
            mock_decode.assert_called_once_with(
                "mock.jwt.token",
                "mock-public-key",
                algorithms=["RS256"],
                issuer=issuer,
                audience=audience,
                options={"require": ["exp", "iat", "iss", "aud"]},
                leeway=10
            )

    @pytest.mark.asyncio
    async def test_verify_token_with_unknown_audience(self):
        """Test token verification when audience is not in payload."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT payload without 'aud' field
        mock_payload = {
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "iss": "https://example.com",
            "sub": "user123"
        }
        
        # Mock signing key
        mock_signing_key = MagicMock()
        mock_signing_key.key = "mock-public-key"
        
        with patch.object(verifier._jwk_client, 'get_signing_key_from_jwt', return_value=mock_signing_key):
            with patch.object(verifier, '_decode_and_validate_jwt', return_value=mock_payload):
                result = await verifier.verify_token("mock.jwt.token")
                
                assert result is not None
                assert result.client_id == "unknown"  # Default value when 'aud' is missing

    @pytest.mark.asyncio
    async def test_verify_token_with_no_expires_at(self):
        """Test token verification when exp field is not in payload."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT payload without 'exp' field
        mock_payload = {
            "aud": "test-client",
            "iat": int(datetime.utcnow().timestamp()),
            "iss": "https://example.com",
            "sub": "user123"
        }
        
        # Mock signing key
        mock_signing_key = MagicMock()
        mock_signing_key.key = "mock-public-key"
        
        with patch.object(verifier._jwk_client, 'get_signing_key_from_jwt', return_value=mock_signing_key):
            with patch.object(verifier, '_decode_and_validate_jwt', return_value=mock_payload):
                result = await verifier.verify_token("mock.jwt.token")
                
                assert result is not None
                assert result.expires_at is None  # None when 'exp' is missing

    def test_jwks_client_initialization(self):
        """Test that PyJWKClient is properly initialized with the endpoint."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        with patch('semgrep_mcp.token_verifier.PyJWKClient') as mock_jwk_client_class:
            mock_jwk_client = MagicMock()
            mock_jwk_client_class.return_value = mock_jwk_client
            
            verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
            
            mock_jwk_client_class.assert_called_once_with(jwks_endpoint)
            assert verifier._jwk_client == mock_jwk_client

    @pytest.mark.asyncio
    async def test_verify_token_logging(self):
        """Test that appropriate logging occurs during token verification."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        # Mock JWT payload
        mock_payload = {
            "aud": "test-client",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "iss": "https://example.com",
            "sub": "user123"
        }
        
        # Mock signing key
        mock_signing_key = MagicMock()
        mock_signing_key.key = "mock-public-key"
        
        with patch('semgrep_mcp.token_verifier.logger') as mock_logger:
            with patch.object(verifier._jwk_client, 'get_signing_key_from_jwt', return_value=mock_signing_key):
                with patch.object(verifier, '_decode_and_validate_jwt', return_value=mock_payload):
                    await verifier.verify_token("mock.jwt.token")
                    
                    # Verify debug logging for token and payload
                    mock_logger.debug.assert_any_call("JWT token: mock.jwt.token")
                    mock_logger.debug.assert_any_call(f"JWT payload: {mock_payload}")

    @pytest.mark.asyncio
    async def test_verify_token_warning_logging_on_failure(self):
        """Test that warning logging occurs when token verification fails."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        with patch('semgrep_mcp.token_verifier.logger') as mock_logger:
            with patch.object(verifier._jwk_client, 'get_signing_key_from_jwt', return_value=None):
                await verifier.verify_token("mock.jwt.token")
                
                # Verify warning logging for missing signing key
                mock_logger.warning.assert_called_with("Could not retrieve signing key from JWKS")

    def test_decode_and_validate_jwt_warning_logging_on_error(self):
        """Test that warning logging occurs when JWT validation fails."""
        jwks_endpoint = "https://example.com/.well-known/jwks.json"
        issuer = "https://example.com"
        audience = "test-client"
        
        verifier = JWKSTokenVerifier(jwks_endpoint, issuer, audience)
        
        with patch('semgrep_mcp.token_verifier.logger') as mock_logger:
            with patch('jwt.decode', side_effect=jwt.InvalidSignatureError("Invalid signature")):
                verifier._decode_and_validate_jwt("mock.jwt.token", "mock-public-key")
                
                # Verify warning logging for JWT validation error
                mock_logger.warning.assert_called_with("JWT validation error: Invalid signature")
