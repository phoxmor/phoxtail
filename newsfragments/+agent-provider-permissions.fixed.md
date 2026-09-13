The inference-provider, model-artifact and agent-settings endpoints at
`/api/agent/v1/` asked for nothing beyond being authenticated, so any account
with a session or an unrestricted token could add a provider or repoint a
site's default model. Each endpoint now names the permission its act needs —
`phoxtail_agent.view_inferenceprovider` and its add/change/delete siblings,
the `modelartifact` equivalents, and `view_agentsitesetting` /
`change_agentsitesetting` — and a refusal names the permission missing.
Chat is unchanged: it stays browser-only and keeps its own `access_chatbot`
check.
