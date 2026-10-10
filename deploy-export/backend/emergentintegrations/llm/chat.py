"""Standalone LLM chat shim — mirrors the emergentintegrations API used by server.py,
backed by the official Anthropic + OpenAI SDKs.

Exposes: LlmChat, UserMessage, ImageContent, TextDelta, StreamDone.
The `provider`/`model` passed to with_model() select which SDK is used; the actual
model id comes from ANTHROPIC_MODEL / OPENAI_MODEL env vars (so you control them).
"""
import os

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat")
# Hybrid cost control: cheap text model by default, vision model ONLY when images
# are actually attached to the request.
OPENROUTER_VISION_MODEL = os.environ.get("OPENROUTER_VISION_MODEL", "openai/gpt-4o-mini")
MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "2048"))


def _detect_mime(b64: str) -> str:
    head = (b64 or "")[:16]
    if head.startswith("iVBOR"):
        return "image/png"
    if head.startswith("/9j/"):
        return "image/jpeg"
    if head.startswith("UklGR"):
        return "image/webp"
    if head.startswith("R0lGOD"):
        return "image/gif"
    return "image/jpeg"


class ImageContent:
    def __init__(self, image_base64: str):
        self.image_base64 = image_base64


class UserMessage:
    def __init__(self, text: str, file_contents=None):
        self.text = text
        self.file_contents = file_contents or []


class TextDelta:
    def __init__(self, content: str):
        self.content = content


class StreamDone:
    def __init__(self, content: str = ""):
        self.content = content


class LlmChat:
    def __init__(self, api_key=None, session_id=None, system_message=""):
        self.system_message = system_message or ""
        self.provider = "anthropic"
        self.model = None

    def with_model(self, provider, model):
        self.provider = provider
        self.model = model
        return self

    async def stream_message(self, um):
        imgs = getattr(um, "file_contents", []) or []
        if self.provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            content = []
            for ic in imgs:
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": _detect_mime(ic.image_base64), "data": ic.image_base64},
                })
            content.append({"type": "text", "text": um.text})
            async with client.messages.stream(
                model=ANTHROPIC_MODEL, max_tokens=MAX_TOKENS,
                system=self.system_message,
                messages=[{"role": "user", "content": content}],
            ) as stream:
                async for text in stream.text_stream:
                    if text:
                        yield TextDelta(text)
            yield StreamDone()
        else:
            # OpenAI-compatible providers: "openrouter" (primary, cheapest) or "openai".
            from openai import AsyncOpenAI
            if self.provider == "openrouter":
                client = AsyncOpenAI(
                    api_key=os.environ["OPENROUTER_API_KEY"],
                    base_url="https://openrouter.ai/api/v1",
                    default_headers={
                        "HTTP-Referer": os.environ.get("APP_URL", "https://interview-ai-engine"),
                        "X-Title": os.environ.get("APP_TITLE", "Interview AI Engine"),
                    },
                )
                model = self.model or OPENROUTER_MODEL
                # Hybrid: switch to a vision-capable model only when images are attached,
                # so routine text turns stay on the cheapest text model.
                # Free entries keep their model: openrouter/free auto-picks a vision-capable free model.
                if imgs and not (model.endswith(":free") or model == "openrouter/free"):
                    model = OPENROUTER_VISION_MODEL
            else:
                client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
                model = OPENAI_MODEL
            content = [{"type": "text", "text": um.text}]
            for ic in imgs:
                mime = _detect_mime(ic.image_base64)
                content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{ic.image_base64}"}})
            messages = [{"role": "system", "content": self.system_message}, {"role": "user", "content": content}]
            stream = await client.chat.completions.create(
                model=model, messages=messages, stream=True, max_tokens=MAX_TOKENS,
            )
            async for chunk in stream:
                delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
                if delta:
                    yield TextDelta(delta)
            yield StreamDone()
