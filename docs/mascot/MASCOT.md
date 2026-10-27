# Zhipu — the GLM-Videos mascot

Zhipu (智谱) is the mascot of the GLM-Videos project: **the Z.ai logo tile come to life.**
Wherever GLM turns plain words into films, Zhipu is the little spark that does the work —
it lives in the terminal, hops into the Z.ai app, reviews diffs, runs previews and checks
its own work. It is an **original character design** created for this project (MIT licence,
see the repo `LICENSE`); it is not derived from any other company's mascot, and it borrows
nothing but the Z.ai brand palette. The Z.ai name, logo and interface belong to Z.ai —
Zhipu is an unofficial fan character, which is why every film that stars it carries the
"unofficial fan film" credit.

Zhipu is designed to be rendered in **any visual style** — pixel art, flat vector, 2.5D,
full 3D, paper, neon, engraving — because its identity lives in three things that survive
every restyle: the **charcoal tile silhouette**, the **white face and Z emblem**, and the
**signal-blue glow**. This document is the single source of truth for drawing it.

---

## 1. The palette — straight from the Z mark

The palette is sampled from the official Z.ai logo (charcoal rounded square, white Z).
Everything Zhipu wears is one of these six tokens; nothing else is allowed on the character.

| Token | Hex | Role on the character | Notes |
|---|---|---|---|
| `INK` | `#2D2D2D` | The body: one rounded-square tile (the logo square) | Neutral charcoal — never tinted warm or cool |
| `WHITE` | `#FFFFFF` | Eyes, mouth/smile, the chest Z emblem | The Z is always white on charcoal, exactly like the logo |
| `ZAI` | `#1F63EC` | Signal blue: antenna glow, eye glints, chest core band (pixel form) | The "spark" colour; also the accent in UI/demo scenes |
| `ZAI_D` | `#1849C8` | Deep signal blue: feet, antenna stem, shading of blue parts | Derived shade of `ZAI` |
| `ZAI_L` | `#257AF1` | Light signal blue: highlights, sparks, confetti pairs | Derived tint of `ZAI` |
| `INK_D` | `#141414` | Charcoal shadow tone (bottom shading of the tile) | Derived shade of `INK` |

On dark backgrounds, lift the blues instead of the charcoal: use `#6E96F5` (ZAI),
`#A9C4FA` (ZAI_L) and keep `INK` as `#2D2D2D` — the tile must stay the darkest solid
shape on screen so it reads as "the logo tile". The deep-navy `#0B1B2B` is reserved for
ink/line-work effects (speech-burst outlines, dots, pencils) where a near-black that is
slightly cooler than `INK` is wanted.

Contrast, for accessibility: white on `#2D2D2D` is ≈ 12.6:1, `#1F63EC` on `#2D2D2D` is
≈ 2.9:1 (fine for decorative glow, never for text), `#1F63EC` on white is ≈ 5.2:1.

## 2. Construction — the canonical geometry

All variants are the **same drawing at different render fidelities**:

- **The tile** — one rounded square, width ≈ height. Corner radius ≈ 13–14 % of the side
  (the logo tile's ratio). The tile is head and body in one block; Zhipu has no neck.
- **The face** — on the upper half of the tile: two rounded-square white eyes with a small
  `ZAI` pupil/glint each, and a short white smile. Eyes sit above the tile's midline.
- **The Z emblem** — on the lower half of the chest, white, traced from the official Z
  mark (three strokes: top bar, diagonal, bottom bar). It is the only mark on the body.
  At pixel scale (18×10) there is no room for the strokes, so the emblem simplifies to
  the **blue core band**; from flat 2D upward the true Z is drawn.
- **The antenna** — one thin `ZAI_D` stem from the tile's top edge, ending in a glowing
  `ZAI` knob: the wisdom spark. In 2.5D/3D it gains a halo and a specular highlight.
- **The arms** — two stubby charcoal capsules (`INK`) on the tile's sides; they can pose
  (down, up, wave, tuck) but never grow hands or fingers.
- **The feet** — two chunky rounded `ZAI_D` blocks under the tile. No legs; feet attach
  directly, which is what makes the silhouette read as a floating app icon.

Proportion check for any redraw: tile ≈ 47 % of total height, antenna ≈ 18 %,
feet ≈ 12 %, and the Z emblem's width ≈ 31 % of the tile width.

## 3. The style kit — one mascot, every style

The kit lives in this folder; the pixel engine lives with the demo film.

| Variant | File | Use it for |
|---|---|---|
| **Pixel (18×10)** | `styles/living-screencast/demo/zhipu.js` · `docs/zhipu.svg` | Pixel-art and screencast styles; the JS module is the animated sprite (poses, blinks, walk cycles, sparks) and exports the palette tokens (`INK`, `ZAI`, `ZAI_D`, `ZAI_L`, `EYE`, `GLOW`) |
| **Flat 2D — master** | `docs/mascot/zhipu-flat.svg` | The canonical reference drawing; UI art, README, avatars, stickers, print |
| **2.5D** | `docs/mascot/zhipu-2p5d.svg` | Motion-graphics and papercraft feels: same geometry plus top-light gradient, rim light, soft ground shadow |
| **3D** | `docs/mascot/zhipu-3d-hero.png` · `docs/mascot/zhipu-3d-wave.png` | Cinematic styles and key art; generated references — re-render from the flat master when you need new poses |
| **Wordmark** | `docs/glm-videos-logo.svg` | The repo logo: pixel Zhipu + "GLM-Videos" |

### How to adapt Zhipu to a new style

The rule that makes the mascot style-proof: **the style owns the rendering technique,
the brand owns the palette and the silhouette.** Concretely:

1. **Start from the flat master** (or the pixel grid if the style is low-res) and re-draw
   in the target technique — engraving hatching, art-deco gold linework, neon tubes,
   newsprint halftone, clay render, whatever the film calls for.
2. **Keep the trio intact.** In monochrome styles, charcoal tile + white marks is the
   floor; the blue may drop to a single accent (the antenna glow) or go metallic gold in
   an art-deco pass — but the body never takes another hue.
3. **Keep the read.** At any distance the drawing must resolve to: dark rounded square,
   white face, white Z, one glowing point on top. If a restyle breaks that read
   (busy hatching over the face, glow lost in a bright scene), simplify the style, not
   the mascot.
4. **Resolution ladder.** 18×10 px → blue core band, no Z. ≥ 64 px → Z emblem appears.
   3D → the tile may get soft bevels and the Z slight embossing, but the tile stays a
   tile (do not turn it into a rounded humanoid robot).
5. **Costume is allowed, transformation is not.** Zhipu can wear a leather cap and goggles
   (Wings, 1927), sit in a cockpit, carry a flashlight — as long as the tile silhouette,
   the white face and the palette survive underneath.

### The pixel sprite API (quick reference)

`zhipu.js` exports `grid()`, `sprite()`, `pixels()`, `pixart()` plus effect helpers
(`SPARK`, `BANG`, `HEART`, …) — see the file header. Poses: `eyes: n|r|l|u|d|wide|blink|
happy|shut`, `arms: down|up|wave|tuck`, `legs: stand|walkA|walkB|tuck|none`. Kinds on the
grid: 1 charcoal body · 2 white eye/mouth · 3 blue glow · 4 blue glint · 5 blue core ·
6 deep-blue foot. The terminal logo in the demo film is drawn from the **same grid**
(Zhipu's own silhouette), so the "logo comes alive" incarnation shot stays in sync by
construction.

## 4. Do / Don't

**Do**

- Use `#2D2D2D` for the tile even on light backgrounds — the contrast is the brand.
- Keep the Z white; on blue backgrounds where white is scarce, outline the Z in `ZAI`
  instead of recolouring the tile.
- Light the antenna knob as the brightest point of the character in every style.
- Pair Zhipu with the demo-scene accent rules: chapter wipes and sparks use the blue trio
  (`#1F63EC / #1849C8 / #257AF1`).

**Don't**

- Don't tint the body toward navy, brown or orange (that is another company's clay).
- Don't give Zhipu fingers, a nose, ears, or clothes that hide the Z emblem.
- Don't reuse any other mascot's pixel grid or silhouette — Zhipu's 18×10 grid and the
  logo-tile geometry are original to this project and must stay so.
- Don't render the Z emblem rotated or mirrored.

## 5. Licence and credit

The Zhipu character, its pixel grid, its flat/2.5D/3D drawings and this guide are original
work of the GLM-Videos project and ship under the repo's MIT licence. The Z.ai brand
palette is used to match the platform's visual identity; Z.ai's name, logo and interface
remain the property of Z.ai. Films that star Zhipu are unofficial fan films and say so in
their credits.
