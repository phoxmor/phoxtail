The `phoxtail hatch` wizard no longer offers to create the admin account
when the database step failed or was skipped, since the account has
nowhere to go; it is listed as a next step instead. A step that failed
also keeps its reason, such as "migrate failed", in the final summary.
