"""
One-time script: generates an embedding for every concept in the database
and saves it back to Supabase's new `embedding` column.

Run this once now, and again any time you add new concepts later.
"""
import os
import time
from dotenv import load_dotenv
from supabase import create_client
import google.generativeai as genai

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768  # must match the vector(768) column we created in Supabase


def embed_text(text: str):
    """Turns a piece of text into a 768-number embedding using Gemini."""
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )
    return result["embedding"]


def main():
    # fetch every concept currently in the database
    response = supabase.table("concepts").select("*").execute()
    concepts = response.data
    print(f"Found {len(concepts)} concepts.")

    for i, concept in enumerate(concepts):
        # combine the most meaningful fields into one piece of text to embed
        # (this gives the embedding richer context than the word alone)
        text_to_embed = (
            f"{concept['word']}: {concept['meaning']}. "
            f"Relevant when: {concept['human_experience']}"
        )

        try:
            embedding = embed_text(text_to_embed)
        except Exception as e:
            print(f"  FAILED on '{concept['word']}': {e}")
            continue

        supabase.table("concepts").update({"embedding": embedding}).eq(
            "id", concept["id"]
        ).execute()

        print(f"  [{i + 1}/{len(concepts)}] embedded: {concept['word']}")
        time.sleep(0.5)  # small pause to stay comfortably under rate limits

    print("Done! All concepts now have embeddings.")


if __name__ == "__main__":
    main()