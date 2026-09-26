# Image / Vision testing rules (Anthropic base64 via emergentintegrations)

- Accepted MIME: image/jpeg, image/png, image/webp only.
- Send frame 1 only for animated images.
- Resize before base64 encoding to avoid multi-MB payloads.
- Never send blank or solid-colour images.
- Frontend sends a data URL; backend strips the `data:...;base64,` prefix before ImageContent.
- Vision output must follow the strict format: `[RÉPONSE : X]` + `• Logique :` + `• À prononcer :`.
