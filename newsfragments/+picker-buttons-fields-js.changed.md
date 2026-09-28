The calendar and clock buttons of date, date-time and time boxes open the
browser's picker through the shared `phoxtail_core/js/fields.js`, instead of an
inline script on every button. A page that draws such a box must include
`phoxtail_core/scripts.html`, as it already must for the password toggle.
