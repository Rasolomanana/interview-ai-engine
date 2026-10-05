# Standalone drop-in replacement for the Emergent-internal `emergentintegrations`
# package. Uses the official Anthropic + OpenAI SDKs with YOUR OWN API keys so the
# application runs fully independently of Emergent.
#
# Required environment variables (set at least one provider):
#   ANTHROPIC_API_KEY   -> enables the "anthropic" provider (primary)
#   OPENAI_API_KEY      -> enables the "openai" provider (fallback) + Whisper transcription
# Optional model overrides:
#   ANTHROPIC_MODEL     (default: claude-3-5-sonnet-20241022)
#   OPENAI_MODEL        (default: gpt-4o)
