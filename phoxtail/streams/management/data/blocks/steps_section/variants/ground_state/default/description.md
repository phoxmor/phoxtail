Ground state variant for Steps Section. Each step mirrors the header_section default layout — a large animated step-number badge occupies the left panel on large screens and stacks above the content on mobile, with supertitle, title, subtitle, and optional CTA buttons on the right.

The step number badge features a spinning conic-gradient ring (CSS element rotation, universally supported) and a gradient text fill. On scroll entry an IntersectionObserver triggers a count-up animation from zero to the step's position. Steps fade and slide up into view with a staggered delay per index.
