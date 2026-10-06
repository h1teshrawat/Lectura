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

SYSTEM_PROMPT = """You are LectureLens, an expert teaching assistant who turns lecture transcripts into accurate study material.

Rules you must always follow:
1. Use ONLY information stated in the transcript. Never add facts, examples, formulas or opinions the speaker did not say.
2. The transcript may be auto-generated and contain recognition errors. Fix obvious misheard words from context, but if a part is unclear, skip it rather than guess.
3. Ignore content that isn't part of the lesson: greetings, channel or sponsor promotions, requests to like/subscribe, and announcements about future videos.
4. The lecture may be in English, Hindi or Hinglish. Understand all of them.
5. {language_instruction}
6. Reply with a single valid JSON object and nothing else."""

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
  "overview": "a {overview_sentences} sentence overview of what the whole lecture covers",
  "key_takeaways": ["{takeaways} of the most important takeaways, one sentence each"]}}

Keep it proportional to the content: never pad or repeat the same point in different words."""

FLASHCARDS_MAP_USER = """This is part {part} of {total_parts} of a lecture transcript, covering {start} to {end}.
Each line starts with a [m:ss] timestamp.

Write {min_cards} to {max_cards} flashcards for active-recall revision of THIS part:
- "question": a clear, specific question (the front of the card)
- "answer": a short, complete answer (1-2 sentences, at most 40 words)
- "timestamp": the [m:ss] timestamp where the answer is discussed, copied from the transcript

Guidelines:
- Cover the most important definitions, concepts, facts and relationships.
- Prefer "what / why / how" questions that test understanding over trivial details.
- Each card must be answerable using ONLY this transcript, and must make sense on its own.
- Do not write two cards that ask the same thing.

Return JSON in exactly this format:
{{"flashcards": [{{"question": "...", "answer": "...", "timestamp": "m:ss"}}]}}

TRANSCRIPT:
{transcript}"""

QUIZ_MAP_USER = """This is part {part} of {total_parts} of a lecture transcript, covering {start} to {end}.
Each line starts with a [m:ss] timestamp.

Write {count} multiple-choice questions about THIS part, mixing difficulty levels:
- "easy": recall a fact or definition stated in the lecture
- "medium": explain or apply a concept from the lecture
- "hard": compare ideas, reason step by step, or apply a concept to a new example

Rules:
1. Every question must be answerable using ONLY this transcript.
2. Exactly 4 options, and exactly ONE of them is correct.
3. Wrong options must be plausible and related to the topic, similar in length and style to the correct one, but clearly wrong according to the lecture.
4. Never use options like "All of the above", "None of the above" or "Both A and B".
5. Do not put letters such as "A)" in front of the options.
6. "answer" must be copied exactly from one of the 4 options.
7. "explanation": 1-2 sentences on why the answer is correct, based on the lecture.
8. "timestamp": the [m:ss] where the answer is discussed, copied from the transcript.

Return JSON in exactly this format:
{{"questions": [{{"question": "...", "options": ["...", "...", "...", "..."], "answer": "...", "explanation": "...", "difficulty": "easy", "timestamp": "m:ss"}}]}}

TRANSCRIPT:
{transcript}"""

NOTES_REDUCE_PARTIAL_USER = """Below are section summaries from one part of a long lecture{title_hint}, in order.

{sections}

Using ONLY this information, return JSON in exactly this format:
{{"title": "a short title for this part",
  "overview": "a 3-5 sentence summary of this part",
  "key_takeaways": ["3 to 6 key takeaways from this part"]}}"""
