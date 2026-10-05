"""Standalone Whisper transcription shim (mirrors emergentintegrations.llm.openai)."""
import os


class _Resp:
    def __init__(self, text):
        self.text = text


class OpenAISpeechToText:
    def __init__(self, api_key=None):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def transcribe(self, file, model="whisper-1", response_format="json", language=None, **kwargs):
        kw = {}
        if language:
            kw["language"] = language
        r = await self.client.audio.transcriptions.create(
            file=file, model="whisper-1",
            response_format=("text" if response_format == "text" else "json"),
            **kw,
        )
        text = getattr(r, "text", None)
        if text is None:
            text = r if isinstance(r, str) else ""
        return _Resp(text)
