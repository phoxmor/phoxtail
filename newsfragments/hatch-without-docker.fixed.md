`phoxtail hatch` checks for uv before it writes anything, so an existing
directory it was asked to overwrite is no longer deleted first. The setup
wizard checks Docker once, up front, including whether it is running and
this user may use it. Without it the wizard still generates the project
configuration, skips the steps that need Docker, and lists what to install
or start first. Before, it went on to offer each step that needs Docker,
and each one it ran failed without saying why. The wizard also stops the
database container its database step starts, when you skip creating the
admin account or interrupt it with Ctrl-C.
