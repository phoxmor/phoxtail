`phoxtail.core.clocks.localize(value, zone)` reads a datetime given for a
place on its local clocks. A time without an offset is read in the zone, but
refused when the zone's clocks skip it or show it twice; a time with an offset
is kept only when the offset is the zone's at that moment. Each refusal is a
`ValidationError` naming the offset to send, which the API answers with 422.
`phoxtail.core.clocks.ON_LOCAL_CLOCKS` states the rule, for the description
of an API field or MCP tool that takes such times.
