# Gaia — Yoga & Pilates Studio

A warm, grounded palette set for Gaia, a yoga and pilates studio. The design direction draws from
the natural world — earth, plant, stone, and morning light — creating an atmosphere of calm,
vitality, and embodied presence. Saturation is kept deliberately low-to-medium throughout; this
is not a palette that shouts, but one that invites.

The earthy warmth of the surface and secondary tones is balanced by the muted green primary and
cool mist info palette, preventing the overall feel from becoming heavy or rustic. The result is
organic without being naive, and refined without being clinical.

## Role Mapping

| Role        | Palette    | File          |
|-------------|------------|---------------|
| Surface     | `linen`    | linen.yaml    |
| Primary     | `fern`     | fern.yaml     |
| Secondary   | `clay`     | clay.yaml     |
| Accent      | `saffron`  | saffron.yaml  |
| Success     | `moss`     | moss.yaml     |
| Warning     | `ochre`    | ochre.yaml    |
| Destructive | `hibiscus` | hibiscus.yaml |
| Info        | `mist`     | mist.yaml     |

## Palette Rationale

### Surface — Linen
A warm, natural off-white at H≈35° with very low saturation. Evokes undyed linen, cotton, and
natural paper — materials associated with studios, wellness spaces, and handmade quality. Light
shades (50–200) serve as page and card backgrounds; mid-tones (400–600) work for borders and
muted text; dark shades (800–950) replace pure black in body copy to keep warmth consistent.

### Primary — Fern
A muted earthy green at H≈140°, deliberately desaturated compared to the typical "wellness
green". Full saturation reads as energetic and sporty; fern sits closer to the grey-green of
actual foliage — more contemplative, more grounded. The 500 shade (`#527c57`) clears AA contrast
on white. Use 700+ for body text; 400–500 for filled buttons and interactive states.

### Secondary — Clay
Warm terracotta at H≈18°. The complementary pairing with fern (~122° apart) gives the system
visual tension without conflict. Clay reads as handmade, earthy, and physical — well suited to
a studio that emphasises embodied movement. The 500 shade (`#cd5840`) is rich enough for
prominent UI elements without crossing into alarming red territory.

### Accent — Saffron
A deep, saturated golden yellow at H≈40°. Saffron is used sparingly — highlights, active tab
indicators, pricing callouts, and special offer banners. Its warmth amplifies the earthy
quality of the palette as a whole; a cooler accent (blue, violet) would introduce incongruous
energy. The 500 shade (`#e89a08`) achieves approximately 3.5:1 on white — use for decorative
elements rather than critical text labels.

### Success — Moss
A darker forest-moss green at H≈128°, clearly distinct from the fern primary despite both being
green families. Moss anchors further toward yellow-green (H≈128° vs fern's H≈140°) and is
noticeably more saturated at mid-tones, ensuring success states read as categorically different
from brand elements. The 500 shade (`#3a8f33`) achieves AA contrast on white backgrounds.

### Warning — Ochre
An earthy amber-yellow at H≈36°. Ochre communicates caution through the same warm amber
convention as gold and amber in other sets, but in a more mineral, less metallic register. The
500 shade (`#d48808`) is warm and clear without approaching the intensity of saffron, keeping
the two distinct in practice.

### Destructive — Hibiscus
A botanical warm pink-red at H≈348°. Unlike a fully saturated signal red, hibiscus retains
the warmth and bloom quality of the flower it is named for — still clearly alarming at the 500
shade (`#e03d6e`), but appropriate for a wellness context where clinical severity would feel
out of place. Lighter shades (50–200) function as destructive banner backgrounds; darker shades
for text on those backgrounds.

### Info — Mist
A cool blue-grey at H≈205°, low-to-medium saturation. Provides necessary contrast with the
otherwise warm palette — when something is mist-coloured, it reads immediately as neutral and
informational rather than branded. The name and hue evoke early morning, stillness, and
openness: an appropriate register for tooltips, help text, and system notifications in a
wellness product.
