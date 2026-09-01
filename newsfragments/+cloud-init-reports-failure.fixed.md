`phoxtail server provision` no longer reports a successful bootstrap when
cloud-init failed. It now asks cloud-init for its status instead of checking
for a file that is written either way, and the bootstrap ends on a Docker
check so a failed install is visible.
