An action announces what it changed under the model's own name, and what
shows that model listens and redraws itself. `phoxtail.core.htmx.change_event()`
makes the name from the model's Django label (`phoxtail_tokens.accesstoken:changed`);
`changed(Model, message)` answers an action that went through (204, the
change, `closeModal`, a toast); `{% changed_event 'app_label.Model' %}` gives
a listener the same name, and `'AUTH_USER_MODEL'` stands for whichever user
model the project uses. Apps write no event names of their own.
