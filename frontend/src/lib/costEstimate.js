// Rough client-side cost estimator for the interview session. Token counts are
// APPROXIMATE (~4 chars/token) and server prices are editable defaults — the
// displayed figure is an ESTIMATE, not real billing.
const CHARS_PER_TOKEN = 4;
const IMAGE_TOKENS = 800; // rough per-image vision cost

// USD per 1M tokens: [input, output].
export const PRICING = {
  gemini: { in: 0, out: 0 },       // user's own free Google key
  openrouter_free: { in: 0, out: 0 }, // OpenRouter free router
  server: { in: 0.3, out: 1.1 },   // default ~DeepSeek via OpenRouter (paid)
  anthropic: { in: 3, out: 15 },   // Claude Sonnet (last resort)
};

export function estimateTokens(text = "") {
  return Math.ceil((text ? String(text).length : 0) / CHARS_PER_TOKEN);
}

// Lets advanced users override server pricing via localStorage.serverPricing = {in,out}.
function serverPrice() {
  try {
    const o = JSON.parse(localStorage.getItem("serverPricing"));
    if (o && typeof o.in === "number" && typeof o.out === "number") return o;
  } catch { /* ignore */ }
  return PRICING.server;
}

export function estimateTurnCost({ provider, inputText, outputText, imageCount = 0 }) {
  const price = PRICING[provider] && provider !== "server" ? PRICING[provider] : serverPrice();
  const inputTokens = estimateTokens(inputText) + imageCount * IMAGE_TOKENS;
  const outputTokens = estimateTokens(outputText);
  const cost = (inputTokens / 1e6) * price.in + (outputTokens / 1e6) * price.out;
  return { inputTokens, outputTokens, cost };
}
