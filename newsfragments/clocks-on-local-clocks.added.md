`phoxtail.core.clocks.on_local_clocks(zone_path, zones, condition)` asks a
condition of each row on the clocks of its own zone: `condition` is called with
each zone and returns that zone's `Q`, so "ends today or later" is
`lambda zone: Q(end_date__gte=timezone.localdate(timezone=zone))`, each row
compared with the date where it is. The result is a `Q`, to combine with other
conditions. `filter_on_local_clocks` is built on it.
