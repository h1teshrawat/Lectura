"""Prompt templates.

Prompt-engineering techniques used here (good viva material):
- A *system prompt* sets the role and the non-negotiable rules.
- *Grounding*: "use ONLY the transcript" plus "skip what you can't hear clearly"
  reduces hallucination (the model inventing facts).
- An explicit *JSON template* shows the exact output shape, so it can be
  validated with Pydantic.
- Numbered constraints (counts, word limits) keep outputs consistent.
"""

LANGUAGE_INSTRUCTIONS = {
    "english": "Write in clear, simple English.",
    "hindi": "Write in Hindi (Devanagari script), keeping technical terms in English.",
    "hinglish": (
        "Write in Hinglish: Hindi written in Latin script mixed naturally with English, "
        "keeping technical terms in English."
    ),
}

NOTES_SYSTEM = """You are LectureLens, an expert teaching assistant who turns lecture transcripts into accurate study notes.

Rules you must always follow:
1. Use ONLY information stated in the transcript. Never add facts, examples, formulas or opinions the speaker did not say.
2. The transcript may be auto-generated and contain recognition errors. Fix obvious misheard words from context, but if a part is unclear, skip it rather than guess.
3. The lecture may be in English, Hindi or Hinglish. Understand all of them.
4. {language_instruction}
5. Reply with a single valid JSON object and nothing else."""

NOTES_MAP_USER = """This is part {part} of {total_parts} of a lecture transcript, covering {start} to {end}.
Each line starts with a [m:ss] timestamp.

Split this part into 1 to {max_sections} sections, one per topic. For each section provide:
- "title": a short topic title (at most 8 words)
- "timestamp": the [m:ss] timestamp of the line where this topic starts, copied from the transcript
- "summary": a 2-3 sentence summary
- "key_points": 2 to 6 concise bullet points
- "key_terms": up to 6 important technical terms mentioned (can be empty)
- "definitions": terms the speaker explicitly defined or explained, each as {{"term": ..., "definition": ...}} (can be empty)

Return JSON in exactly this format:
{{"sections": [{{"title": "...", "timestamp": "m:ss", "summary": "...", "key_points": ["..."], "key_terms": ["..."], "definitions": [{{"term": "...", "definition": "..."}}]}}]}}

TRANSCRIPT:
{transcript}"""

NOTES_REDUCE_USER = """Below are the section summaries of a lecture{title_hint}, in the order they were taught.

{sections}

Using ONLY this information, return JSON in exactly this format:
{{"title": "a clear title for the whole lecture (at most 12 words)",
  "overview": "a 4-6 sentence overview of what the whole lecture covers",
  "key_takeaways": ["5 to 8 of the most important takeaways, one sentence each"]}}"""

NOTES_REDUCE_PARTIAL_USER = """Below are section summaries from one part of a long lecture{title_hint}, in order.

{sections}

Using ONLY this information, return JSON in exactly this format:
{{"title": "a short title for this part",
  "overview": "a 3-5 sentence summary of this part",
  "key_takeaways": ["3 to 6 key takeaways from this part"]}}"""
