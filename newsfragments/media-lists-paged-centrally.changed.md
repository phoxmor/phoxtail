The image, document, video and audio lists page through the same mechanism
as every other list; what they answer is unchanged. Listing them no longer
costs a database query per item for its tags. `phoxtail content list` takes
`--offset` beside `--limit` for every kind it lists, including locales and
sites, and refuses a limit above 500.
