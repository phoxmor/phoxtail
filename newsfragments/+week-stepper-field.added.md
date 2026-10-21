A `week_stepper` field draws a week for a page that shows one day at a time:
its seven days on one row, each picking its date, two arrows around the
week's dates in the page's language that go to the week before and after, a
calendar that opens the browser's own date picker, and a Today button beside
it (given `today`). The chosen day sits on a circle in the brand colour,
its words in white, that slides to the next, and today's number is in the
brand colour too. The three groups share one
card and a row where they fit, and take rows of their own where they do
not, the room they have deciding it, never the screen's width; the
calendar and the arrows line up with the days below them. The circles never
shrink: where seven do not fit side by side, the days scroll sideways
inside the card, faded at a side with more days beyond it, the chosen day
in the middle when first shown, the row kept where it was after that, and
the page itself never grows wider. On one row the days keep their own width
in the middle, and a card made wider than it needs (a page may stretch it across a row) gives the
room to their sides, the calendar and Today at its start and the arrows at
its end; on two rows or more its corners are softer than a pill's. Its date box takes its own id,
so a filter form on the same page can offer the same date for any day. Any
date field given `hx_trigger="step"` now sends a picked day at once and a
typed one on Enter or when the field is left, as the steppers' boxes do.
