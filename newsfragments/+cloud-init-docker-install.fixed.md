`phoxtail server provision` now installs Docker on images that ship `grub-pc`
with a stored install device that doesn't exist. The failed bootloader upgrade
left `dpkg` half-configured, and a half-configured `dpkg` fails every later
`apt-get`, Docker's included. The bootstrap now declines that install rather
than attempting it, leaving the bootloader as the image shipped it, and acts
only when the stored device is invalid — so healthy images are untouched.
