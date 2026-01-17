import os
import re
import httpx
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Body, Query
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "kryonex-backend",
        "timestamp": datetime.utcnow().isoformat()
    }

# ENV VARIABLES (FROM RAILWAY)
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
KRYONEX_SECRET = os.getenv("KRYONEX_SECRET")
RETELL_FROM_NUMBER = os.getenv("RETELL_FROM_NUMBER", "+12185795523")


class LeadPayload(BaseModel):
    name: str
    phone: str
    service_interest: str = "General Inquiry"

def normalize_phone(raw: str) -> str:
    """
    Accepts inputs like:
    - (419) 924-3016
    - 4199243016
    - 1-419-924-3016
    - +14199243016
    Returns E.164 like +14199243016 (defaults to US if 10 digits).
    """
    if not raw:
        raise HTTPException(status_code=400, detail="Missing phone")

    s = raw.strip()

    # Keep leading + if present, then strip everything else to digits
    if s.startswith("+"):
        digits = "+" + re.sub(r"\D", "", s[1:])
    else:
        digits_only = re.sub(r"\D", "", s)
        # If it's 11 digits and starts with 1, treat as US
        if len(digits_only) == 11 and digits_only.startswith("1"):
            digits = "+" + digits_only
        # If it's 10 digits, assume US
        elif len(digits_only) == 10:
            digits = "+1" + digits_only
        # If it's longer, assume caller forgot +
        elif len(digits_only) > 10:
            digits = "+" + digits_only
        else:
            raise HTTPException(status_code=400, detail=f"Invalid phone format: {raw}")

    return digits

async def fire_retell_call(payload: LeadPayload) -> dict:
    # Hard stop if env is missing (saves you from silent failures)
    if not RETELL_API_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: RETELL_API_KEY missing")
    if not RETELL_AGENT_ID:
        raise HTTPException(status_code=500, detail="Server misconfigured: RETELL_AGENT_ID missing")

    phone = normalize_phone(payload.phone)

    url = "https://api.retellai.com/v2/create-phone-call"
    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "from_number": RETELL_FROM_NUMBER,
        "to_number": phone,
        "agent_id": RETELL_AGENT_ID,
        "retell_llm_dynamic_variables": {
            "customer_name": payload.name,
            "service": payload.service_interest
        }
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(url, json=data, headers=headers)
            resp.raise_for_status()
            j = resp.json()
            return {"status": "success", "call_id": j.get("call_id"), "to": phone}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=500, detail=f"Retell Failure: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Retell Network Error: {str(e)}")

# HEALTH CHECK
@app.get("/")
async def health_check():
    return {"status": "active", "system": "KRYONEX_SNIPER_V1"}

# ✅ FUNNEL ENDPOINT (GET) — THIS FIXES YOUR "METHOD NOT ALLOWED"
# Use this in GHL form "Redirect to URL"
@app.get("/funnel/call")
async def funnel_call(
    token: str = Query(...),
    phone: str = Query(...),
    name: str = Query("New Lead"),
    service: str = Query("General Inquiry")
):
    if not KRYONEX_SECRET:
        raise HTTPException(status_code=500, detail="Server misconfigured: KRYONEX_SECRET missing")

    if token != KRYONEX_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = LeadPayload(name=name, phone=phone, service_interest=service)
    return await fire_retell_call(payload)

# DEBUG CALL (POST) — header auth (works in Postman/curl)
@app.post("/debug/test-call")
async def debug_call(
    phone: str = Body(..., embed=True),
    x_api_key: str = Header(None)
):
    if x_api_key != KRYONEX_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = LeadPayload(name="TEST_USER", phone=phone, service_interest="DEBUG_TEST")
    return await fire_retell_call(payload)

# MAIN WEBHOOK (POST) — for GHL Webhooks (header auth)
@app.post("/webhook/trigger-call")
async def trigger_call(
    payload: LeadPayload,
    x_api_key: str = Header(None)
):
    if x_api_key != KRYONEX_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return await fire_retell_call(payload)
