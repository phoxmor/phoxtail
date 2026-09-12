The dashboard's API is now found by convention rather than declared: it ships
`phoxtail/dashboard/api/` naming its versions, and `api_version_router` is gone
from its app config. The endpoints are unchanged.
