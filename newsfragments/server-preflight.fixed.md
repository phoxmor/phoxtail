`phoxtail server provision` checks for ssh and ssh-keygen before it asks
the provider for anything, so a missing program no longer surfaces after a
paid server already exists. `phoxtail server deploy` and `phoxtail server
ssl` check for ssh and scp before they change anything on the server. Both
also generate their configuration with the running phoxtail itself, not
whichever `phoxtail` comes first on `PATH`: that could be another install,
or none at all when it was started as `python -m phoxtail`.
