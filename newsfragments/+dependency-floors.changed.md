Every declared dependency floor now names a version phoxtail is tested against,
replacing inherited minimums that had never been installed — several of which
did not work. Installing phoxtail alongside an older pinned dependency will now
fail to resolve rather than fail at import.
