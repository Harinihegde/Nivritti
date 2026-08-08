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

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768  # must match the vector(768) column in Supabase

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

    # Step B (NEW): turn the user's input into an embedding
    try:
        embed_result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=req.userInput,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBEDDING_DIMENSIONS,
        )
        query_embedding = embed_result["embedding"]
    except Exception as e:
        print("gemini error (embedding user input):", e)
        return {"error": "The AI service is unavailable right now. Please try again shortly."}

    # Step C (NEW): ask Supabase's match_concepts function for the closest concept
    # by real vector similarity — no more sending the whole list to Gemini
    try:
        match_response = supabase.rpc(
            "match_concepts",
            {"query_embedding": query_embedding, "match_count": 1},
        ).execute()
        matches = match_response.data
    except Exception as e:
        print("supabase error (vector search):", e)
        return {"error": "Could not load concepts. Please try again shortly."}

    if not matches:
        return {"error": "No concepts found"}

    chosen = matches[0]

    # Step E: ask Gemini for the warm "bridge text" — unchanged
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

    # Step F: log this exploration in the database — unchanged
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

    # Step G: send it all back — unchanged
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