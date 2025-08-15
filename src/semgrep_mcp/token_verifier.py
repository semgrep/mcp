"""JWT token verifier implementation using JWKS validation."""

import logging
from typing import Any

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.shared.auth_utils import resource_url_from_server_url

logger = logging.getLogger(__name__)

class JWKSTokenVerifier(TokenVerifier):
    """JWT token verifier that uses JWKS for signature validation.

    This implementation validates JWT tokens by:
    1. Using PyJWKClient to automatically fetch and cache public keys from JWKS
    2. Validating the JWT signature
    3. Checking standard JWT claims (exp, iat, iss, aud)
    """

    def __init__(
        self,
        jwks_endpoint: str,
        issuer: str,
        server_url: str,
    ):
        self.jwks_endpoint = jwks_endpoint
        self.issuer = issuer
        self.server_url = server_url

        # Initialize PyJWKClient for automatic JWKS handling
        self._jwk_client = PyJWKClient(self.jwks_endpoint)

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify JWT token using JWKS validation."""

        try:
            # Log payload for debugging
            logger.debug(f"JWT token: {token}")

            # Get the signing key from JWKS
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            if not signing_key:
                logger.warning("Could not retrieve signing key from JWKS")
                return None

            # Decode and validate the JWT
            payload = self._decode_and_validate_jwt(token, signing_key.key)
            if not payload:
                return None

            # Log payload for debugging
            logger.debug(f"JWT payload: {payload}")

            return AccessToken(
                token=token,
                client_id=payload.get("aud", "unknown"),
                scopes=["openid", "profile", "email"],
                expires_at=payload.get("exp"),
            )

        except Exception as e:
            logger.warning(f"JWT validation failed: {e}")
            return None

    def _decode_and_validate_jwt(self, token: str, public_key: Any) -> dict | None:
        """Decode and validate JWT using the public key."""
        try:
            # Decode JWT with validation
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"], # NEVER CHANGE THIS or read from the token
                issuer=self.issuer,  # Validate issuer
                audience=resource_url_from_server_url(self.server_url),  # Validate audience
                options={
                    "require": ["exp", "iat", "iss", "aud"],
                    "verify_signature": True,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": False, # TODO: Verify audience (need to figure out how to do this since Cursor does dynamic client registration)
                },
                leeway=10,
            )

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidIssuerError:
            logger.warning("Invalid JWT issuer")
            return None
        except jwt.InvalidAudienceError:
            logger.warning("Invalid JWT audience")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.warning(f"JWT validation error: {e}")
            return None
