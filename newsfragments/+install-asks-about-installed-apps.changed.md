`phoxtail install` now asks whether the package belongs in `INSTALLED_APPS`
instead of deciding for you. A package can be a Django app without carrying any
of the files that give one away, and no inspection can rule that out, so the
detection result is offered as the default answer rather than acted on. Answer
no and nothing is registered; answer yes for a package that was not detected
and you are asked for the module name. `--app <module>` and `--no-app` answer
ahead of time, and a non-interactive run acts on the detection result without
prompting. The
stream-population step follows the same answer: declining registration skips
it instead of running it against an app Django does not know about.
