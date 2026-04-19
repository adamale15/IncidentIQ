"""
LLM answer generation with simple streaming support.
"""
import asyncio
from typing import AsyncGenerator, Dict

import google.generativeai as genai

from app.config import settings
from app.generation.prompts import build_prompt


genai.configure(api_key=settings.GEMINI_API_KEY)


class LLMGenerator:
    """Generate answers from assembled context."""

    def __init__(self):
        self.flash_model = genai.GenerativeModel(settings.GEMINI_FLASH_MODEL)
        self.pro_model = genai.GenerativeModel(settings.GEMINI_PRO_MODEL)

    def _select_model(self, query_type: str):
        if query_type in ["comparison", "timeline"]:
            return self.pro_model
        return self.flash_model

    async def generate_answer(self, question: str, context: str, query_type: str) -> Dict[str, str]:
        prompt = build_prompt(question, context, query_type)
        model = self._select_model(query_type)
        loop = asyncio.get_event_loop()

        def _sync_generate() -> str:
            response = model.generate_content(prompt)
            return response.text

        text = await loop.run_in_executor(None, _sync_generate)
        model_used = settings.GEMINI_PRO_MODEL if query_type in ["comparison", "timeline"] else settings.GEMINI_FLASH_MODEL
        return {"answer": text, "model_used": model_used}

    async def stream_answer(self, question: str, context: str, query_type: str) -> AsyncGenerator[str, None]:
        result = await self.generate_answer(question, context, query_type)
        answer = result["answer"]
        chunk_size = 120
        for i in range(0, len(answer), chunk_size):
            yield answer[i : i + chunk_size]
