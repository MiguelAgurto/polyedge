from supabase import Client, create_client

from polyedge.config import Settings


def get_client(settings: Settings) -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required outside dry-run")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
