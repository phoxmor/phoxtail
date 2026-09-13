Page-schema contributors are listed in `page_schemas` in an app's `api/`
package, beside the `versions` that declare its routers, instead of as dotted
strings in `PhoxtailAppConfig.page_schema_contributors`. The attribute is gone.
**Breaking** for any app still declaring it; the contributors become ordinary
imports, so a renamed factory now fails at startup rather than silently.
