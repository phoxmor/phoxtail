`phoxtail.core.clocks.filter_on_local_clocks(queryset, zone_path, zones, **lookups)`
asks a question in clock times of each row on its own clocks: with a bare
`datetime(2026, 11, 1)` in `start_datetime__gte`, a row in Athens and a row in
Berlin each count from midnight where they happen, which Django's `__date` and
`Trunc` — one zone per query — cannot say. The caller passes the zones its rows
can be at; each turns the bound into one instant, so the database still
compares instants. A bound with an offset is kept as that one moment. A bound
the clocks skip starts where they resume, and a repeated one is its first
showing, or its second for an upper bound. Clock times inside a
list (`__range`, `__in`) and parts of a datetime (`__date`, `__hour`, …),
which Django reads in one zone, are refused with `TypeError`.
