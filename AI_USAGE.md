# AI usage

The current prototype does not call an AI provider. All booking decisions, priority handling, conflict checks, schedule values, and rescheduling values are deterministic application data and rules.

If AI assistance is added later, it may interpret English or Hinglish request text, ask for missing details, prefill a draft, or explain a deterministic decision. AI must never validate a schedule, invent room availability, change priority, grant permissions, approve a request, or write schedule changes directly. All model output must remain a reviewable draft and pass normal server-side validation and authorization.

No prompts or model API keys are stored in this repository. Production model/provider configuration must be documented when enabled.
