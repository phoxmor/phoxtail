The agent app now declares its API the same way every other phoxtail app does.
Its endpoints used to be hidden entirely when the optional `chatbot` extra was
not installed; `providers`, `artifacts` and `settings` never needed that
dependency and are now served in every project.
