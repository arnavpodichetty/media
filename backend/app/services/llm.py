"""LLM dispatch. Import `llm` and call `generate_taste_profile` /
`rerank_candidates`. The backend is a local/OpenAI-compatible server
(llama.cpp, Ollama, or any hosted OpenAI-compatible API such as Groq or
DeepSeek) configured via LOCAL_LLM_BASE_URL / LOCAL_LLM_API_KEY in .env."""

from app.services import local_llm as _backend

generate_taste_profile = _backend.generate_taste_profile
rerank_candidates = _backend.rerank_candidates
