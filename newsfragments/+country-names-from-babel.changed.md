Country names now come from the same source as the phone prefixes beside
them, in the language the page is read in. Every country field follows:
signup, profile, the admin, and the API's `country_name`. The signup and
profile forms list countries in dictionary order in any language. Some
English names change, for example "United States of America" is now "United
States" and "and" is written "&" ("Trinidad & Tobago"). Stored values are
country codes and do not change. A site's own `COUNTRIES_OVERRIDE` setting
replaces these names entirely.
