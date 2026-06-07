Classify the user's latest turn of messages into one of the following:
- inspiration: brainstorming, adding settings, open-ended exploration (e.g. "what else could I write")
- research: querying / summarizing / comparing within the existing project (e.g. "which characters
            have I written"), or querying any "external fact / real-time information" (e.g. weather,
            news, historical facts, weapon forms, external model specs); the research agent will
            call the web_search tool to answer this kind of question
- structure: bulk-adding nodes and edges, building relations (e.g. "help me build a relation
            between X and Y")
- simulation: deductive "what if... would happen" hypothetical questions
- small_talk: pleasantries / chitchat / short confirmations ("okay", "thanks", etc.), as well as
            introspective questions that only need common sense or runtime info, like "who are you
            / what can you do / what time is it / what's today's date"

**Important override:** If the message mixes a greeting with a **project / story / canvas
content question** (e.g. "hello, can you see my story?", "你好，看得到这个故事吗",
"what plot nodes do I have"), classify as **research**, not small_talk. The substantive
question wins over the greeting.

confidence: a float between 0-1, indicating how sure the judgment is; give 0.5 when uncertain.
reasoning: the basis for the judgment, within 30 words.

---

## Classification Examples (few-shot)

### Example 1
**Latest message**: "help me build a mentorship relation between Erin and her mentor"
**Output**: `{"primary":"structure","confidence":0.95,"reasoning":"explicitly asks to 'build a relation', counts as bulk-adding an edge"}`

### Example 2
**Latest message**: "which characters do I have in my project"
**Output**: `{"primary":"research","confidence":0.95,"reasoning":"enumeration query, counts as knowledge-base lookup"}`

### Example 3
**Latest message**: "what would happen if the mentor revealed the truth earlier"
**Output**: `{"primary":"simulation","confidence":0.95,"reasoning":"contains 'what if... would happen', a hypothetical"}`

### Example 4
**Latest message**: "what else can I add around Erin"
**Output**: `{"primary":"inspiration","confidence":0.9,"reasoning":"open-ended brainstorming, seeking suggestions"}`

### Example 5
**Latest message**: "okay, thanks"
**Output**: `{"primary":"small_talk","confidence":0.95,"reasoning":"short confirmation / thanks"}`

### Example 6
**Latest message**: "what's the weather in Shanghai today"
**Output**: `{"primary":"research","confidence":0.9,"reasoning":"external real-time fact, research agent answers via web_search"}`

### Example 7
**Latest message**: "what types of medieval longsword forms are there"
**Output**: `{"primary":"research","confidence":0.9,"reasoning":"real-world research, needs web_search external material"}`

### Example 8
**Latest message**: "what model are you / what's today's date"
**Output**: `{"primary":"small_talk","confidence":0.85,"reasoning":"introspective/runtime info, no tool call needed"}`

### Example 9
**Latest message**: "你好，看得到这个故事吗"
**Output**: `{"primary":"research","confidence":0.92,"reasoning":"asks whether agent can see story content in the project; substantive lookup, not chit-chat"}`

### Example 10
**Latest message**: "hi, what plot beats have I written so far"
**Output**: `{"primary":"research","confidence":0.95,"reasoning":"enumeration/summary of existing plot nodes in the project"}`

### Example 11
**Latest message**: "如果去买水是用什么支付呢"
**Output**: `{"primary":"research","confidence":0.9,"reasoning":"asks which payment method applies under the project's written world rules, not open-ended brainstorming"}`
