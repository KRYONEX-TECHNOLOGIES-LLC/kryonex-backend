import os
import httpx
from fastapi import FastAPI, HTTPException, Header, Body
from pydantic import BaseModel

app = FastAPI()

# ENV VARIABLES (FROM RAILWAY)
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
KRYONEX_SECRET = os.getenv("KRYONEX_SECRET")

class LeadPayload(BaseModel):
    name: str
    phone: str
    service_interest: str = "General Inquiry"

# HEALTH CHECK
@app.get("/")
async def health_check():
    return {"status": "active", "system": "KRYONEX_SNIPER_V1"}

# DEBUG CALL (TEST YOUR PHONE)
@app.post("/debug/test-call")
async def debug_call(
    phone: str = Body(..., embed=True),
    x_api_key: str = Header(None)
):
    if x_api_key != KRYONEX_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = LeadPayload(name="TEST_USER", phone=phone, service_interest="DEBUG_TEST")
    return await trigger_call(payload, x_api_key)

# MAIN WEBHOOK (GHL)
@app.post("/webhook/trigger-call")
async def trigger_call(
    payload: LeadPayload,
    x_api_key: str = Header(None)
):
    if x_api_key != KRYONEX_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    phone = payload.phone.strip()
    if not phone.startswith("+"):
        phone = f"+1{phone}" if len(phone) == 10 else f"+{phone}"

    url = "https://api.retellai.com/v2/create-phone-call"

    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "from_number": "+12185795523",
        "to_number": phone,
        "agent_id": RETELL_AGENT_ID,
        "retell_llm_dynamic_variables": {
            "customer_name": payload.name,
            "service": payload.service_interest
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return {"status": "success", "call_id": response.json().get("call_id")}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=500, detail=f"Retell Failure: {e.response.text}")
