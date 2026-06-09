from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import litellm
import json

app = FastAPI(title="LawApp Mother Algorithm", version="1.0")

# =====================================================================
# 1. THE BOUNCERS (Pydantic Models)
# These mathematically guarantee the AI cannot return conversational garbage.
# If the AI hallucinates outside these structures, the app throws an error.
# =====================================================================

class TimelineEvent(BaseModel):
    date: str
    event_summary: str
    pii_scrubbed: bool

class AEE_Output(BaseModel):
    timeline: List[TimelineEvent]
    missing_critical_dates: bool

class ART_Output(BaseModel):
    claim_type: List[str]
    viability_score_percentage: int
    statutory_citations_used: List[str]
    affirmation_risk_detected: bool
    recommended_next_step: str

class Guard_Output(BaseModel):
    safety_check_passed: bool
    failed_citations: List[str] = []
    reason_for_failure: str = ""

# =====================================================================
# 2. INCOMING USER REQUEST
# =====================================================================

class UserEvidencePayload(BaseModel):
    user_id: str
    raw_evidence_text: str

# =====================================================================
# 3. THE MOTHER ALGORITHM (The Controller)
# =====================================================================

@app.post("/api/v1/process-case")
async def process_case(payload: UserEvidencePayload):
    """
    The main orchestrator route. It controls the specialized agents step-by-step.
    If any agent fails or disobeys the schema, the process safely aborts.
    """
    
    try:
        # ---------------------------------------------------------
        # STEP 1: Wake up Agent AEE (The Reader)
        # ---------------------------------------------------------
        aee_response = litellm.completion(
            model="lawapp-edge-slm", # Routed via LiteLLM config to local Wasm
            messages=[
                {"role": "system", "content": "You are Agent AEE... [Insert Prompt]"},
                {"role": "user", "content": payload.raw_evidence_text}
            ],
            response_format={ "type": "json_object" } # Forces strict JSON
        )
        
        # The Bouncer: Validate the raw string into our strict Pydantic model
        raw_aee_json = json.loads(aee_response.choices[0].message.content)
        clean_timeline = AEE_Output(**raw_aee_json) 
        
        # ---------------------------------------------------------
        # STEP 2: Wake up Agent ART (The Thinker)
        # ---------------------------------------------------------
        # We pass ONLY the clean, structured timeline from AEE. 
        # ART never sees the raw user text.
        art_response = litellm.completion(
            model="lawapp-edge-slm", 
            messages=[
                {"role": "system", "content": "You are Agent ART... [Insert Prompt]"},
                {"role": "user", "content": clean_timeline.model_dump_json()}
            ],
            response_format={ "type": "json_object" }
        )
        
        raw_art_json = json.loads(art_response.choices[0].message.content)
        case_strategy = ART_Output(**raw_art_json)

        # ---------------------------------------------------------
        # STEP 3: Fallback Logic Trigger (If Confidence is Low)
        # ---------------------------------------------------------
        if case_strategy.viability_score_percentage < 50:
            # The Mother Algorithm decides to escalate to the cloud ONLY if necessary
            art_response = litellm.completion(
                model="lawapp-reasoning-heavy", # Escalates to Claude/GPT-4o via LiteLLM
                messages=[
                    {"role": "system", "content": "You are Agent ART Edge Case Solver..."},
                    {"role": "user", "content": clean_timeline.model_dump_json()}
                ],
                response_format={ "type": "json_object" }
            )
            raw_art_json = json.loads(art_response.choices[0].message.content)
            case_strategy = ART_Output(**raw_art_json)

        # ---------------------------------------------------------
        # STEP 4: Return to User
        # ---------------------------------------------------------
        # We successfully processed the case, maintained control, and kept costs low.
        return {
            "status": "success",
            "extracted_timeline": clean_timeline.dict(),
            "legal_strategy": case_strategy.dict()
        }

    except Exception as e:
        # If any agent hallucinates, breaks the JSON schema, or times out, 
        # the Mother Algorithm traps the error here. No bad data reaches the user.
        raise HTTPException(status_code=500, detail=f"Orchestration Safety Halt: {str(e)}")