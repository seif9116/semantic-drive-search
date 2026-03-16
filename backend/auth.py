from pathlib import Path
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from backend.config import settings

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_PATH = Path("token.json")

# Store the active flow so the same instance (with code_verifier) is used
# for both authorization URL generation and token exchange.
_active_flow: Flow | None = None


def get_auth_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = settings.redirect_uri
    return flow


def get_authorization_url() -> tuple[str, str]:
    global _active_flow
    _active_flow = get_auth_flow()
    url, state = _active_flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url, state


def exchange_code(code: str) -> Credentials:
    global _active_flow
    flow = _active_flow or get_auth_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    _save_token(creds)
    _active_flow = None
    return creds


def get_credentials() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)

    if creds and creds.valid:
        return creds

    return None


def _save_token(creds: Credentials):
    TOKEN_PATH.write_text(creds.to_json())


def is_authenticated() -> bool:
    creds = get_credentials()
    return creds is not None and creds.valid


def clear_credentials():
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
