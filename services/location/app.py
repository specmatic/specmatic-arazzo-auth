from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlmodel import Session, select

from common.config import settings
from common.db.models import UserRow
from common.db.session import get_session
from common.http.errors import install_error_handler
from common.vault.client import read_kv2

app = FastAPI(title="Location API", version="1.0.0")
install_error_handler(app)
bearer = HTTPBearer(auto_error=False)
LOCATION_BEARER_TOKEN = settings.location_bearer_token


class Location(BaseModel):
    userId: int
    locationCode: str


@app.on_event("startup")
def load_location_secret() -> None:
    global LOCATION_BEARER_TOKEN
    vault_addr = settings.commerce_vault_addr
    vault_token = settings.commerce_vault_token
    if vault_addr and vault_token:
        secret = read_kv2(vault_addr, vault_token, "commerce")
        LOCATION_BEARER_TOKEN = secret["location_bearer_token"]


def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    if credentials is None or credentials.credentials != LOCATION_BEARER_TOKEN:
        raise HTTPException(status_code=401, detail={"message": "Missing or invalid bearer token"})


@app.get("/location", response_model=Location, operation_id="getLocation")
def get_location(
    user_email: str = Query(..., alias="userEmail", min_length=1),
    _: None = Depends(authorize),
    session: Session = Depends(get_session),
) -> Location:
    row = session.exec(select(UserRow).where(UserRow.user_email == user_email)).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"message": "User was not found"})
    return Location(userId=row.user_id, locationCode=row.location_code)


@app.get("/healthz", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
