import os
from dotenv import load_dotenv
from supabase import create_client

# load the values from .env into the program
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# this "supabase" object is what we'll use everywhere to talk to the database
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

import google.generativeai as genai
from fastapi import FastAPI
from pydantic import BaseModel

# --- set up Gemini, same as before ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

# --- create the actual web app ---
app = FastAPI()

from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/moments")
def moments_page(request: Request):
    return templates.TemplateResponse(request, "moments.html")


# this describes what data we expect the frontend to send us
class ExploreRequest(BaseModel):
    userInput: str
    sessionId: str = "anonymous"


@app.post("/api/explore")
def explore(req: ExploreRequest):
    if not req.userInput.strip():
        return {"error": "No input provided"}

    # Step B: fetch every Sanskrit concept from the database
    try:
        response = supabase.table("concepts").select("*").execute()
        concepts = response.data
    except Exception as e:
        print("supabase error (fetching concepts):", e)
        return {"error": "Could not load concepts. Please try again shortly."}

    if not concepts:
        return {"error": "No concepts found"}

    # Step C: build a numbered list, and ask Gemini to pick the best match
    concept_list = "\n".join(
        f"{i}. {c['word']} — {c['meaning']} (relates to: {c['human_experience']})"
        for i, c in enumerate(concepts)
    )

    selection_prompt = f"""A person said: "{req.userInput}"
Here are Sanskrit concepts numbered 0 to {len(concepts) - 1}:
{concept_list}
Reply with only the number of the single most relevant concept. Nothing else."""

    try:
        selection_result = model.generate_content(selection_prompt)
        index_text = selection_result.text.strip()
    except Exception as e:
        print("gemini error (selection):", e)
        return {"error": "The AI service is unavailable right now. Please try again shortly."}

    try:
        concept_index = min(max(int(index_text), 0), len(concepts) - 1)
    except ValueError:
        concept_index = 0

    chosen = concepts[concept_index]

    # Step E: ask Gemini for the warm "bridge text"
    bridge_prompt = f"""A person said: "{req.userInput}"
The Sanskrit concept is {chosen['word']} ({chosen['script']}).
Its meaning: {chosen['meaning']}
How it relates to human experience: {chosen['human_experience']}
Write 2-3 sentences connecting this concept to what they shared.
Be warm and curious, not preachy or instructional.
Write as if you just remembered something that might be useful to them.
Do not explain Sanskrit. Do not teach. Just connect."""

    try:
        bridge_result = model.generate_content(bridge_prompt)
        bridge_text = bridge_result.text.strip()
    except Exception as e:
        print("gemini error (bridge text):", e)
        return {"error": "The AI service is unavailable right now. Please try again shortly."}

    # Step F: log this exploration in the database
    exploration_id = None
    try:
        insert_response = (
            supabase.table("explorations")
            .insert({
                "session_id": req.sessionId,
                "user_input": req.userInput,
                "concept_id": chosen["id"],
                "ai_bridge_text": bridge_text,
            })
            .execute()
        )
        exploration_id = insert_response.data[0]["id"] if insert_response.data else None
    except Exception as e:
        # not fatal — the user still gets their result, they just won't be able to save it
        print("supabase error (logging exploration):", e)

    # Step G: send it all back
    return {
        "concept": chosen,
        "bridgeText": bridge_text,
        "explorationId": exploration_id,
    }


class SaveRequest(BaseModel):
    explorationId: str


@app.patch("/api/explore")
def save_exploration(req: SaveRequest):
    try:
        supabase.table("explorations").update({"saved": True}).eq(
            "id", req.explorationId
        ).execute()
    except Exception as e:
        print("supabase error (saving):", e)
        return {"error": "Could not save. Please try again shortly."}
    return {"success": True}


@app.get("/api/moments")
def get_moments(sessionId: str = ""):
    if not sessionId:
        return {"moments": []}

    # fetch saved explorations for this session, joined with their concept details
    try:
        response = (
            supabase.table("explorations")
            .select("id, user_input, ai_bridge_text, created_at, concepts(word, script, meaning)")
            .eq("session_id", sessionId)
            .eq("saved", True)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as e:
        print("supabase error (fetching moments):", e)
        return {"moments": []}

    return {"moments": response.data}