# Phoxtail — Technology Platform

A crisp, cool-tinted palette set for the Phoxtail product site, which presents the platform's
technology to potential clients and partners. The design direction inherits the green+neutral
sensibility from early prototypes (Tailwind `emerald` + `neutral`) and refines each colour into
something distinctive and ownable — moving away from generic Tailwind defaults toward a coherent
system with clear personality.

The aesthetic is modern, precise, and trustworthy. Hues are chosen for their associations with
technology, innovation, and reliability. Unlike the earthy `core` set, saturation is allowed to
breathe here — interfaces selling software products benefit from the energy that slightly more vivid
colours provide, as long as they remain balanced and purposeful.

## Role Mapping

| Role        | Palette      | File            |
|-------------|--------------|-----------------|
| Surface     | `cool-slate` | cool-slate.yaml |
| Primary     | `verdant`    | verdant.yaml    |
| Secondary   | `iris`       | iris.yaml       |
| Accent      | `cobalt`     | cobalt.yaml     |
| Success     | `jade`       | jade.yaml       |
| Warning     | `gold`       | gold.yaml       |
| Destructive | `crimson`    | crimson.yaml    |
| Info        | `azure`      | azure.yaml      |

## Palette Rationale

### Surface — Cool Slate
Tailwind's `neutral` (which the early prototypes used) is a pure, hue-less gray — technically
correct but forgettable. `cool-slate` adds a barely-perceptible blue undertone at H≈213° with only
~3% saturation. The difference is almost invisible in isolation, but when placed alongside the
teal-green primary and violet secondary it creates subconscious coherence — the backgrounds feel
like they belong to the same world as the brand colours. Whites feel like a high-resolution monitor
rather than a sheet of paper.

### Primary — Verdant
The early prototypes used Tailwind's `emerald` (H≈160°). `verdant` shifts this slightly toward
teal at H≈168°, which gives it a more distinctly digital and precise character — closer to the
green of terminal interfaces and environmental technology dashboards. The 500 shade (`#0da47c`)
is slightly darker and more saturated than emerald's `#10b981`, lending more weight to primary
buttons and interactive elements. Like all green palettes, shades 500 and 600 have limited
contrast against white (a property of the green channel's high luminosity contribution); use
700+ for text on white backgrounds.

### Secondary — Iris
Chosen for maximum hue contrast with verdant (~97° apart on the colour wheel), iris is the
classic pairing for technology products built on a green primary. It carries strong associations
with creativity, innovation, and craft — evident in tools like VS Code, GitHub, and Linear. The
500 shade (`#7a50e8`) is tuned dark enough to achieve AA contrast (~5:1) against white, making
it suitable for secondary button labels without relying on a darker variant.

### Accent — Cobalt
A deep, rich blue at H≈220°. Distinct from both the violet secondary and the sky info colour,
cobalt sits in the "interactive emphasis" register — focus rings, active tab indicators, selected
states, and link underlines. Its depth (500: `#1d68f0`) ensures it is never mistaken for a
decorative element; when something is cobalt, it is asking to be clicked.

### Success — Jade
The most deliberate decision in this set. Because the primary is green (verdant), a conventional
success green risks blending with brand elements and creating confusion. `jade` solves this by
anchoring at H≈130° — pure grass green — placing it 38° away from verdant's H≈168° teal-green.
At small sizes (status badges, checkmark icons) the two greens read as clearly different families.
At larger sizes (success banners) the contextual cues (icon, label, placement) reinforce the
distinction further.

### Warning — Gold
A warm golden amber at H≈37°. No significant departure from convention here — gold is universally
understood as "caution" and anything more experimental risks reducing legibility of system state.
The 500 shade (`#e08408`) is rich and saturated enough to demand attention without becoming
aggressive.

### Destructive — Crimson
A fully saturated, unambiguous red at H≈5°. Unlike the `rust` palette in the earthy `core` set,
`crimson` is given no warm-tone softening. Technology users expect error states to be immediately
and unambiguously red; any attempt to make it "on-brand" introduces hesitation at exactly the
moment the interface needs to communicate urgency. The 500 shade (`#e8272e`) achieves high
contrast against both white and dark backgrounds.

### Info — Azure
A cyan-leaning sky blue at H≈200°. The shift toward cyan (away from cobalt's H≈220°) creates
clear role separation: cobalt says "interact with this", azure says "here is some context". The
lighter shades (50–200) work well as info banner backgrounds without overwhelming the content
inside them.
