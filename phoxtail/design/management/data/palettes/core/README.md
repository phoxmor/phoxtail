# Core — Architect & Technical Office

A warm, earthy palette set designed for architectural and technical office mockups. The overarching
aesthetic draws from natural building materials — travertine, fired clay, aged brass, patinated
copper, and forest undergrowth — to create an environment that feels grounded, professional, and
timeless without leaning into the cold neutrality common in generic corporate templates.

Every hue in this set is deliberately desaturated relative to its Tailwind counterpart. Architects
work with physical materials that have complex, muted undertones; vivid digital colours feel
out of place in that context. The result is a palette that photographs well, prints well, and sits
comfortably alongside imagery of buildings, blueprints, and textured surfaces.

## Role Mapping

| Role        | Palette       | File              |
|-------------|---------------|-------------------|
| Surface     | `warm-stone`  | warm-stone.yaml   |
| Primary     | `sand`        | sand.yaml         |
| Secondary   | `sage`        | sage.yaml         |
| Accent      | `brass`       | brass.yaml        |
| Success     | `forest`      | forest.yaml       |
| Warning     | `terracotta`  | terracotta.yaml   |
| Destructive | `rust`        | rust.yaml         |
| Info        | `steel`       | steel.yaml        |

## Palette Rationale

### Surface — Warm Stone
Tailwind's `stone` was the closest built-in option but still slightly too cold and uniform. This
custom version pulls the lighter shades (50–200) a touch warmer and creamier — think aged plaster
and limestone walls — while keeping the darker shades (700–950) almost identical to stone. The
result is a surface palette that makes white backgrounds feel like paper rather than a screen, which
suits architectural presentation.

### Primary — Sand
The client brief called for beige as the primary brand colour. `sand` is a full 11-shade ramp built
around a warm sandy tan (500: `#bc8c45`). The lighter end (50–200) is the "beige" the eye
immediately reads; the mid-to-dark range (500–700) provides sufficient contrast for white-text
buttons and interactive elements (~9:1 against white at 500). The hue sits at H≈33–38°, which keeps
it warm and organic without tipping into orange.

### Secondary — Sage
Muted olive-green at H≈85–90°, heavily desaturated. Architects reach for olive and sage constantly —
it appears in foliage shown in renderings, patinated copper cladding, and moss on stone. Placed
alongside sand, sage creates a natural earth-tone duet without competing for attention. The 500 shade
(`#6f8c46`) reads clearly as green while remaining quiet enough to never overpower the primary.

### Accent — Brass
The one palette in this set with meaningful saturation. Brass (H≈40–42°, mid-high saturation) is
chosen because it is literally a building material — door handles, light fixtures, nameplates — and
it pops with just enough contrast against both the sand primary and the warm-stone surface to serve
as a reliable highlight colour for active states and selected elements. Used sparingly, it adds a
premium, material quality to the interface.

### Success — Forest
A mossy, desaturated forest green (H≈130–140°). Kept muted to stay within the earthy aesthetic
rather than using a vivid "traffic light" green that would clash with the warm tones. Sufficient
hue distance from sage (secondary) at ~45–50° apart means the two greens read as distinct even
at small sizes.

### Warning — Terracotta
Fired terracotta clay (H≈20–25°). The obvious earthy warning colour for this palette — it is
literally a building material. At 500 (`#c75420`) it is warm and unmistakably cautionary without
the neon quality of a standard orange alert.

### Destructive — Rust
Oxidised iron red at H≈10–15°. Slightly cooler and more muted than a pure signal red, it fits
the material palette while still reading unambiguously as danger/error. The warmth in the red
prevents it from feeling clinical or out of place alongside terracotta and sand.

### Info — Steel
Architectural blueprint blue (H≈210–215°), the only cool-hued palette in the set. It is kept at
low saturation so it does not visually compete with the warm tones. The 500 shade (`#3d7099`) reads
as a calm, trustworthy informational blue — close in spirit to the colour of a technical drawing on
tracing paper.
