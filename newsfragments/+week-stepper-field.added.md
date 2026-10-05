A `week_stepper` field draws a week for a page that shows one day at a time:
its seven days on a track, each picking its date, two arrows around the
week's dates in the page's language that go to the week before and after, a
calendar that opens the browser's own date picker, and a Today button beside
it (given `today`). The chosen day sits on a circle that slides to the
next. The three groups share one card and a row where they fit, and take rows
of their own where they do not; the circles never shrink, and where seven do
not fit side by side the days break into rows. Its date box takes its own id,
so a filter form on the same page can offer the same date for any day. Any
date field given `hx_trigger="step"` now sends a picked day at once and a
typed one on Enter or when the field is left, as the steppers' boxes do.
