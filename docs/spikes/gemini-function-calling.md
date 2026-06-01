# Spike: Gemini 1.5 Pro function calling

**Author:** Kautilya  
**Sprint:** 1    
**Status:** Complete  

---

## What this spike answers

Before writing the Phase 2 chat-service, we needed to understand:

1. How to define a tool schema the Vertex AI SDK will accept
2. How to tell whether Gemini's response is a tool call or a final text answer
3. How to complete the multi-turn loop (send result back, get grounded answer)
4. What Gemini does when it decides the tool isn't needed

The script at `scripts/spikes/gemini_function_calling.py` demonstrates all four against a fake `search_knowledge_base` tool that returns hard-coded Document360-style articles.

---

## Running it

```bash
# Authenticate first
gcloud auth application-default login
gcloud config set project molli-dev

# Run from repo root
uv run python scripts/spikes/gemini_function_calling.py
```

Expected output (abbreviated):

```
────────────────────────────────────────────────────────────
USER:  How do I reset my Google Workspace password?
────────────────────────────────────────────────────────────
TOOL CALL: search_knowledge_base({"query": "Google Workspace password reset"})
TOOL RESULT: [
  {
    "title": "Google password reset and account recovery",
    "content": "To reset your Google Workspace password...",
    "source": "Preiss Central / IT / Google Account Recovery"
  }
]

FINAL ANSWER:
To reset your Google Workspace password, go to accounts.google.com ...
(Source: Google password reset and account recovery — Preiss Central / IT)

────────────────────────────────────────────────────────────
USER:  Hi! What can you help me with?
────────────────────────────────────────────────────────────
TOOL CALL: (none — Gemini answered directly)

FINAL ANSWER:
Hi! I'm Molli, Preiss's employee assistant. I can help you with ...
```

---

## Key patterns for Phase 2

### 1. Tool schema definition

Define tools using `FunctionDeclaration` with a JSON Schema `parameters` block. The
`description` fields matter — Gemini uses them to decide when to call the tool.
Be specific: "Search Preiss Central for how-to and policy questions" works better
than "Search for information."

```python
from vertexai.generative_models import FunctionDeclaration, Tool

KB_TOOL = Tool(
    function_declarations=[
        FunctionDeclaration(
            name="search_knowledge_base",
            description="Search Preiss Central for articles that answer employee questions.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query derived from the user's question.",
                    }
                },
                "required": ["query"],
            },
        )
    ]
)
```

Pass the tool to the model at construction time, not per-request:

```python
model = GenerativeModel(
    model_name="gemini-2.0-flash-001",
    tools=[KB_TOOL],
    system_instruction="You are Molli ...",
)
```

### 2. Detecting a tool call vs. a text response

After `model.generate_content(history)`, inspect the parts of the first candidate:

```python
candidate = response.candidates[0]

tool_call_part = None
for part in candidate.content.parts:
    if part.function_call:
        tool_call_part = part
        break

if tool_call_part is None:
    # Gemini answered directly — no tool needed
    final_text = candidate.content.parts[0].text
else:
    fn_name = tool_call_part.function_call.name
    fn_args = dict(tool_call_part.function_call.args)
    # dispatch to your implementation ...
```

**Important:** do not assume `parts[0]` is always text. When Gemini decides to call
a tool, `parts[0]` will be a function call part, not text. Always check by type.

### 3. The multi-turn loop

Gemini's tool-calling pattern requires three turns of conversation history:

```
Turn 1 (user)       → the employee's question
Turn 2 (model)      → Gemini's function_call part  ← this is not a final answer
Turn 3 (user)       → the function_response part with your tool's return value
Turn 4 (model)      → Gemini's final grounded answer  ← this is what you show the user
```

In code:

```python
# Turn 1 — user question
history = [Content(role="user", parts=[Part.from_text(user_question)])]
response = model.generate_content(history)

# Turn 2 — append Gemini's function_call response to history
history.append(response.candidates[0].content)

# Turn 3 — append your tool's result as a function_response
history.append(
    Content(
        role="user",
        parts=[
            Part.from_function_response(
                name=fn_name,
                response={"result": tool_result},   # tool_result can be any JSON-serialisable value
            )
        ],
    )
)

# Turn 4 — ask Gemini to compose the final answer
final_response = model.generate_content(history)
print(final_response.text)
```

The `history` list is exactly what gets stored in Firestore as conversation memory.
Each session is a growing list of `Content` objects appended after every turn.

### 4. When Gemini skips the tool

With the current system instruction ("always search before answering how-to
questions"), Gemini calls the tool on factual / procedural questions and skips it
for greetings, capability questions, and anything clearly conversational.

Observed behaviour in the spike:

| Question | Tool called? | Notes |
|---|---|---|
| "How do I reset my Google password?" | Yes | Factual how-to |
| "How do I request access to Entrata?" | Yes | Factual how-to |
| "Hi! What can you help me with?" | No | Conversational opener |

If the tool returns an empty list (no matching article), Gemini still composes a
response — it says it couldn't find relevant documentation and suggests a
Freshservice ticket. That's the correct fallback behaviour; no extra logic needed.

### 5. Tool result format

Return a list of dicts from `search_knowledge_base`. Each dict should have at
minimum `title`, `content`, and `source`. Gemini will cite the title naturally
in its final answer if the system instruction asks it to.

In Phase 2, the real implementation will call Vertex AI Vector Search (or pgvector)
and return the top-k chunks in the same shape. The tool schema and the multi-turn
loop do not change.

---

## What to carry into Phase 2

- The `Tool` + `FunctionDeclaration` definition moves into `chat-service/app/tools/`.
- The multi-turn loop (history list management) lives in the chat handler in
  `chat-service/app/main.py` or a dedicated `chat_service/app/conversation.py`.
- Firestore stores the serialised `history` list keyed by `(user_id, session_id)`.
  The `Content` objects are serialisable to dict via `.to_dict()` on each part;
  deserialise with `Content.from_dict()` before passing back to `generate_content`.
- Add a second tool (`create_ticket`) in Phase 2 using the same pattern. Gemini
  will choose between `search_knowledge_base` and `create_ticket` based on whether
  it found a good answer.

---

## Open questions / follow-ups

- [ ] What is the right `top_k` value for Vector Search? Need to test answer quality
  vs. context window cost as the D360 corpus grows.
- [ ] How does Gemini behave when both tools are available and it's unsure? Need a
  spike with two tools before Phase 2 implementation starts.
- [ ] Confirm `Content.to_dict()` / `from_dict()` round-trips cleanly through
  Firestore — test this before wiring up the memory layer.
