"""Google OAuth configuration using Authlib."""

from authlib.integrations.starlette_client import OAuth

from .config import settings

# Initialize OAuth
oauth = OAuth()

# Register Google OAuth provider if credentials are configured
if settings.google_client_id and settings.google_client_secret:
    GOOGLE_CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url=GOOGLE_CONF_URL,
        client_kwargs={"scope": "openid email profile"},
    )
