# Default Booking Schedule Variant

Read-only seven-column weekly grid showing confirmed events for the current week at a chosen location. Rows are scoped to hours that have at least one event, keeping the grid compact. Each event chip displays the service name, start–end time (in the location's timezone), and space name. Service palette colours are applied as a left border accent when available. The grid is horizontally scrollable on small screens. Events are fetched at render time via the `get_weekly_schedule` template tag, which includes recurring event projections via `EventService`.
