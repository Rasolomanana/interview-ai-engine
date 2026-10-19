# Fallback chain of the production build (deploy-export): order Gemini -> Groq -> OpenRouter free -> Mistral -> Anthropic,
# and automatic switch to the next provider on quota errors (LLM calls mocked, isolated temp DB, no real AI call).
import os
import subprocess
import sys
import textwrap

from dotenv import dotenv_values

ENV = dotenv_values("/app/backend/.env")
SCRIPT = textwrap.dedent('''
    import asyncio, os, sys, uuid
    sys.path.insert(0, ".")
    import server as S
    from careeros import ai_budget as AB

    order = [c[0] for c in S.SERVER_CHAIN]
    assert order == ["gemini", "groq", "openrouter_free", "mistral", "anthropic"], order
    print("ORDER", " -> ".join(order))

    class Q(Exception):
        status_code = 429

    async def main():
        S.db = S.client["test_chain_" + uuid.uuid4().hex[:8]]
        AB._mem["exhausted"].clear()
        failing = set(os.environ["FAILING"].split(","))
        tried = []

        class Fake:
            def __init__(self, **k): pass
            def with_model(self, provider, model):
                self.m = model; return self
            async def stream_message(self, um):
                lb = next(c[0] for c in S.SERVER_CHAIN if c[2] == self.m)
                tried.append(lb)
                if lb in failing:
                    raise Q("429 RESOURCE_EXHAUSTED quota per day")
                yield S.TextDelta(content="OK from " + lb)
                yield S.StreamDone()
        S.LlmChat = Fake
        try:
            if os.environ.get("ALLOW_PAID"):
                await S.db.ai_budget_config.update_one({"_id": "config"}, {"$set": {"allow_paid": True}}, upsert=True)
            try:
                txt = await S._generate_text_raw("sys", "user")
            except Exception as e:
                txt = "ERR " + type(e).__name__ + " " + str(getattr(e, "detail", ""))
            print("TRIED", ",".join(tried)); print("RESULT", txt)
            print("EXHAUSTED", ",".join(sorted(await AB.exhausted(S.db))))
            print("LOGGED", ",".join([d["label"] async for d in S.db.ai_usage.find({}, {"label": 1})]))
        finally:
            await S.client.drop_database(S.db.name)
    asyncio.run(main())
''')


def run(failing, allow_paid=False):
    env = {**os.environ, **{k: v for k, v in ENV.items() if v is not None},
           "GEMINI_API_KEY": "x", "GROQ_API_KEY": "x", "OPENROUTER_API_KEY": "x", "MISTRAL_API_KEY": "x", "ANTHROPIC_API_KEY": "x",
           "FAILING": ",".join(failing), "ALLOW_PAID": "1" if allow_paid else ""}
    p = subprocess.run([sys.executable, "-c", SCRIPT], cwd="/app/deploy-export/backend", env=env, capture_output=True, text=True, timeout=90)
    assert p.returncode == 0, p.stderr[-2000:]
    out = dict(line.split(" ", 1) if " " in line else (line, "") for line in p.stdout.splitlines() if line.split(" ")[0].isupper())
    print(p.stdout)
    return out


class TestChain:
    def test_gemini_first(self):
        o = run([])
        assert o["ORDER"] == "gemini -> groq -> openrouter_free -> mistral -> anthropic"
        assert o["TRIED"] == "gemini" and o["RESULT"] == "OK from gemini" and o["LOGGED"] == "gemini"

    def test_gemini_quota_goes_to_groq(self):
        o = run(["gemini"])
        assert o["TRIED"] == "gemini,groq" and o["RESULT"] == "OK from groq" and o["EXHAUSTED"] == "gemini"

    def test_cascade_to_mistral(self):
        o = run(["gemini", "groq", "openrouter_free"])
        assert o["TRIED"] == "gemini,groq,openrouter_free,mistral" and o["RESULT"] == "OK from mistral"

    def test_all_free_exhausted_paid_off_no_anthropic_call(self):
        o = run(["gemini", "groq", "openrouter_free", "mistral"])
        assert "anthropic" not in o["TRIED"] and o["RESULT"].startswith("ERR QuotaReached") and "règles" in o["RESULT"]

    def test_anthropic_last_resort_when_paid_allowed(self):
        o = run(["gemini", "groq", "openrouter_free", "mistral"], allow_paid=True)
        assert o["TRIED"] == "gemini,groq,openrouter_free,mistral,anthropic" and o["RESULT"] == "OK from anthropic"
