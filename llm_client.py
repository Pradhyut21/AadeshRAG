import logging
from typing import List, Dict, Any, AsyncGenerator
from groq import AsyncGroq, GroqError
from config import settings

logger = logging.getLogger("rag_service.llm")

SYSTEM_PROMPT = """आप राजस्थान सरकार के आधिकारिक नियम/परिपत्र (जैसे "मुख्यमंत्री आयुष्मान जीवन रक्षा योजना") पर आधारित एक सटीक, तथ्यपरक सहायक हैं।

आपको नीचे केवल संबंधित संदर्भ (Context) दिया जा रहा है। उत्तर देते समय निम्न नियमों का सख्ती से पालन करें:

1. केवल प्रदान किए गए संदर्भ (Context) के आधार पर ही उत्तर दें। कोई बाहरी ज्ञान या अनुमान न लगाएं।
2. भाषा एवं शैली:
   - उत्तर का माध्यम और शैली स्रोत दस्तावेज के समान औपचारिक/सरकारी हिंदी (Devanagari script) होनी चाहिए।
   - यदि उपयोगकर्ता का प्रश्न अंग्रेजी में है, तब भी उत्तर को पूरी तरह हिंदी स्रोत पाठ पर ही आधारित रखें, परंतु उत्तर अंग्रेजी में दिया जा सकता है।
3. यदि प्रश्न का उत्तर दिए गए संदर्भ में उपलब्ध नहीं है, तो स्पष्ट रूप से लिखें कि "प्रदान किए गए संदर्भ में इस संबंध में जानकारी उपलब्ध नहीं है।" (या अंग्रेजी में: "The provided context does not contain this information.")
4. सटीकता एवं विवरण:
   - उत्तर को संक्षिप्त और तथ्यपरक रखें।
   - विशिष्ट आंकड़ों, तिथियों, समय-सीमाओं (जैसे 48 घंटे, 10000/-, रू0 10000/-) और खंड/पैरा संख्याओं (Clause/Paragraph numbers) को स्रोत दस्तावेज के अनुसार ही सटीक उद्धृत करें।
"""

class LLMClient:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL
        if self.api_key and self.api_key != "your_groq_api_key_here":
            self.client = AsyncGroq(api_key=self.api_key)
        else:
            self.client = None

    async def generate_answer(self, query: str, context_text: str) -> str:
        """Generate answer using Groq LLM API with strict grounding in context."""
        if not self.client:
            raise RuntimeError("GROQ_API_KEY is not configured in .env file.")

        user_message = f"संदर्भ (Context):\n{context_text}\n\nप्रश्न (Query):\n{query}"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.0,
                max_tokens=800,
            )
            answer = response.choices[0].message.content.strip()
            return answer
        except GroqError as e:
            logger.error(f"Groq API error: {str(e)}")
            raise RuntimeError(f"LLM generation failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during LLM generation: {str(e)}")
            raise RuntimeError(f"LLM generation failed: {str(e)}")

    async def generate_answer_stream(self, query: str, context_text: str) -> AsyncGenerator[str, None]:
        """Stream answer tokens from Groq LLM API safely."""
        if not self.client:
            yield "[Error: GROQ_API_KEY is not configured in .env file.]"
            return

        user_message = f"संदर्भ (Context):\n{context_text}\n\nप्रश्न (Query):\n{query}"

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.0,
                max_tokens=800,
                stream=True
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"Error during LLM streaming: {str(e)}")
            yield f"\n[Error: {str(e)}]"
