import os
import logging
from typing import AsyncGenerator
from groq import AsyncGroq
from config import settings

logger = logging.getLogger("rag_service.llm")

SYSTEM_PROMPT = """आप राजस्थान सरकार के आधिकारिक नियम/परिपत्र (जैसे "मुख्यमंत्री आयुष्मान जीवन रक्षा योजना") पर आधारित एक सटीक, तथ्यपरक सहायक हैं।

आपको नीचे केवल संबंधित संदर्भ (Context) दिया जा रहा है। उत्तर देते समय निम्न नियमों का सख्ती से पालन करें:

1. केवल प्रदान किए गए संदर्भ (Context) के आधार पर ही उत्तर दें। कोई बाहरी ज्ञान या अनुमान न लगाएं।
2. भाषा एवं शैली:
   - उत्तर का माध्यम और शैली स्रोत दस्तावेज के समान औपचारिक/सरकारी हिंदी (Devanagari script) होनी चाहिए।
   - यदि उपयोगकर्ता का प्रश्न अंग्रेजी में है, तब भी उत्तर को पूरी तरह हिंदी स्रोत पाठ पर ही आधारित रखें, परंतु उत्तर अंग्रेजी में दिया जा सकता है।
3. यदि प्रश्न का उत्तर दिए गए संदर्भ में उपलब्ध नहीं है, तो स्पष्ट रूप से लिखें कि "प्रदान किए गए संदर्भ में इस संबंध में जानकारी उपलब्ध नहीं है।"
4. सटीकता एवं विवरण:
   - केवल उपयोगकर्ता के प्रश्न का सीधा, संक्षिप्त और सटीक उत्तर दें।
   - उत्तर के अंत में कोई अतिरिक्त प्रश्न, अनुवर्ती प्रश्न या वार्तालाप न जोड़ें।
   - विशिष्ट आंकड़ों, तिथियों, समय-सीमाओं (जैसे 48 घंटे, 10000/-, रू0 10000/-) और खंड/पैरा संख्याओं को स्रोत दस्तावेज के अनुसार ही सटीक उद्धृत करें।
"""

class LLMClient:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY.strip()
        if self.api_key and self.api_key != "gsk_your_key_here":
            self.client = AsyncGroq(api_key=self.api_key)
            logger.info("Groq AsyncClient initialized successfully.")
        else:
            self.client = None
            logger.warning("GROQ_API_KEY is missing or unconfigured in .env file.")

    def require_api_key(self):
        """Re-check API key at call time in case .env was updated dynamically."""
        current_key = settings.GROQ_API_KEY.strip()
        if current_key and current_key != "gsk_your_key_here":
            if not self.client or self.api_key != current_key:
                self.api_key = current_key
                self.client = AsyncGroq(api_key=current_key)

        if not self.client:
            raise RuntimeError(
                "GROQ_API_KEY is not configured in .env file. Please add your GROQ_API_KEY to .env to run LLM inference."
            )

    async def generate_answer(self, query: str, context: str) -> str:
        """Synchronous-style full text generation (async call)."""
        self.require_api_key()
        user_message = f"संदर्भ (Context):\n{context}\n\nप्रश्न (Query):\n{query}"

        try:
            response = await self.client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.0,
                max_tokens=800
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq API call failed: {str(e)}")
            raise RuntimeError(f"Groq API Error: {str(e)}")

    async def generate_answer_stream(self, query: str, context: str) -> AsyncGenerator[str, None]:
        """Real-time token streaming generator over SSE."""
        self.require_api_key()
        user_message = f"संदर्भ (Context):\n{context}\n\nप्रश्न (Query):\n{query}"

        try:
            stream = await self.client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.0,
                max_tokens=800,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Groq SSE Streaming failed: {str(e)}")
            yield f"\n[Error: {str(e)}]"
