
import httpx
from supabase import ClientOptions, create_client

from app.core.config import settings


# Use HTTP/1.1 because it was verified to work with our
# Supabase Storage connection.
_http_client = httpx.Client(
    http2=False,
    timeout=30.0,
)

# Reuse one Supabase client throughout the application.
supabase = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SECRET_KEY,
    options=ClientOptions(
        httpx_client=_http_client,
    ),
)
