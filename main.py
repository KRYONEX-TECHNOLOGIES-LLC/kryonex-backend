# KRYONEX BACKEND - THE "SNIPER RIFLE"
# DEPLOYMENT: Render, Railway, or Vercel
# LANGUAGE: Python 3.10+ (FastAPI)

# --- FILE: requirements.txt ---
# fastapi
# uvicorn
# httpx
# pydantic
# ------------------------------

import os
import httpx
from fastapi import FastAPI, HTTPException, Header, Body
from pydantic import BaseModel

app = FastAPI()

# CONFIGURATION
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID") 
KRYONEX_SECRET = os.getenv("KRYONEX_SECRET") 

class LeadPayload(BaseModel):
    name: str
    phone: str
    service_interest: str = "General Inquiry"

# --- 1. HEALTH CHECK (THE PULSE) ---
@app.get("/")
async def health_check():
    """Instant verify that server is running."""
    return {"status": "active", "system": "KRYONEX_SNIPER_V1"}

# --- 2. DEBUG TRIGGER (TEST YOUR PHONE) ---
@app.post("/debug/test-call")
async def debug_call(
    phone: str = Body(..., embed=True), 
    x_api_key: str = Header(None)
):
    """
    Fire a test call IMMEDIATELY to a number.
    Bypasses the complex GHL payload. 
    Usage: Send JSON {"phone": "+1555..."}
    """
    if x_api_key != KRYONEX_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return await trigger_call(LeadPayload(name="TEST_USER", phone=phone, service_interest="DEBUG_TEST"), x_api_key)

# --- 3. THE MAIN WEBHOOK (GHL CONNECT) ---
@app.post("/webhook/trigger-call")
async def trigger_call(
    payload: LeadPayload, 
    x_api_key: str = Header(None)
):
    """
    The Black Box Entry Point.
    GoHighLevel sends data here. We validate, then fire Retell.
    """
    
    # SECURITY LOCK
    if x_api_key != KRYONEX_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid Key")

    # DATA NORMALIZATION
    phone = payload.phone.strip()
    if not phone.startswith("+"):
        phone = f"+1{phone}" if len(phone) == 10 else f"+{phone}"

    print(f"⚡ TARGET ACQUIRED: {payload.name} ({phone})")

    # RETELL API STRIKE
    url = "https://api.retellai.com/v2/create-phone-call"
    headers = {
        "Authorization": f"Bearer {key_45cc0a44ad962933e56efa3c72a7}",
        "Content-Type": "application/json"
    }
    
    data = {
        "from_number": "+12185795523", # REPLACE WITH YOUR RETELL NUMBER
        "to_number": phone,
        "agent_id": agent_7b3adcf228f8841d016f3d204e,
        "retell_llm_dynamic_variables": {
            "customer_name": payload.name,
            "service": payload.service_interest
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            call_data = response.json()
            print(f"✅ CALL FIRED: {call_data.get('call_id')}")
            return {
                "status": "success", 
                "call_id": call_data.get("call_id"),
                "latency_msg": "Target Acquired. Calling."
            }
        except httpx.HTTPStatusError as e:
            print(f"❌ RETELL ERROR: {e.response.text}")
            raise HTTPException(status_code=500, detail=f"Retell Failure: {e.response.text}")
