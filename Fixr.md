# Fixr — Frontend Design Specification

> AI-powered product finder. Users describe a problem, get the perfect product with a buy link.

---

## 1. Design Identity

### Concept
**"Surgical Utility"** — Fixr is a tool that gets out of your way and gets the job done. The aesthetic is dark, sharp, and confident. No fluff, no decorative noise. Every element earns its place on screen. The accent color — an electric yellow-green — signals intelligence and precision, like a laser pointer on a dark wall.

### Personality
- Smart but not arrogant
- Warm but not chatty
- Fast, focused, frictionless

### What makes it unforgettable
A single glowing dot in the logo that pulses like a heartbeat. It's alive. It's thinking. It's waiting for your problem.

---

## 2. Color System

All colors defined as CSS custom properties on `:root`.

| Token | Hex | Usage |
|---|---|---|
| `--bg` | `#0d0d0f` | Page background |
| `--surface` | `#16161a` | Cards, bubbles, panels |
| `--surface2` | `#1e1e24` | Nested surfaces, product cards |
| `--border` | `#2a2a35` | All borders and dividers |
| `--accent` | `#c8f542` | Primary CTA, links, highlights, the pulse dot |
| `--accent2` | `#7b5cf0` | Input focus ring, bot avatar gradient, glow effects |
| `--text` | `#f0f0f0` | Primary readable text |
| `--muted` | `#7a7a8c` | Secondary text, placeholders, metadata |

### Usage Rules
- Never use `--accent` as a text color on light backgrounds — it's a surface/glow color only
- `--accent2` is never the dominant color; it exists to signal "active/interactive"
- `--border` is the only separator — no shadows as dividers
- Background atmospheric glows: `--accent2` radial at top-center, `--accent` radial at bottom-right — both at very low opacity (7–12%)

---

## 3. Typography

### Font Pairing

| Role | Font | Weight | Source |
|---|---|---|---|
| Display / Headings / Logo / CTAs | **Syne** | 700, 800 | Google Fonts |
| Body / Chat / UI text | **DM Sans** | 300, 400, 500 | Google Fonts |

```html
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap" rel="stylesheet">
```

### Type Scale

| Element | Font | Size | Weight | Notes |
|---|---|---|---|---|
| Logo "Fixr" | Syne | 26px | 800 | Letter-spacing: -0.5px |
| Section headlines | Syne | 22px | 700 | Line-height: 1.3 |
| Product name | Syne | 16px | 700 | Line-height: 1.3 |
| CTA button text | Syne | 13px | 700 | Letter-spacing: 0.3px |
| Body / chat text | DM Sans | 14.5–15px | 400 | Line-height: 1.6 |
| Secondary / muted | DM Sans | 13–14px | 400 | color: `--muted` |
| Labels / caps | DM Sans | 10–12px | 600 | `text-transform: uppercase`, letter-spacing: 1–1.5px |
| Disclaimer | DM Sans | 11px | 400 | color: `#444455` |

---

## 4. Layout & Composition

### Page Structure
```
┌─────────────────────────────────────┐
│  Header (logo left, tagline right)  │  max-width: 720px, centered
├─────────────────────────────────────┤
│                                     │
│         Messages / Chat Feed        │  flex-grow, scrollable
│                                     │
├─────────────────────────────────────┤
│   Sticky Input Bar + Disclaimer     │  sticky bottom, blur fade
└─────────────────────────────────────┘
```

- Max content width: **720px**, centered with `margin: 0 auto`
- Page padding: `0 16px` on mobile, auto-centering on desktop
- The layout is a single vertical column — no sidebars, no grids
- Input area is `position: sticky; bottom: 0` with a gradient fade to background above it

### Spatial Rules
- Generous whitespace inside cards: `padding: 28px` for intro card, `16px` for product card
- Gap between messages: `16px`
- No horizontal rules or decorative dividers except `--border` color borders on components

---

## 5. Components

### 5.1 Logo
```
● Fixr
```
- The dot is a 10×10px circle, `background: --accent`, `border-radius: 50%`
- Animated with `pulse` keyframe: scales 1→1.3→1 with opacity 1→0.7→1 over 2.4s, ease-in-out, infinite
- Box shadow: `0 0 14px var(--accent)` — creates the glow effect
- Logo text in Syne 800, letter-spacing: -0.5px

### 5.2 Intro Card
Shown at the start of every session before the first message.

- Background: `--surface`, border: `1px solid --border`, border-radius: `20px`
- Headline: two lines — first line normal `--text`, second line in `--accent`
- Body text: `--muted`, 14px, line-height 1.6
- Example chips below the body text
- Entry animation: `fadeUp` (see Animations section)

### 5.3 Example Chips
Tappable suggestion pills below the intro headline.

- Background: `--surface2`, border: `1px solid --border`, border-radius: `100px`
- Padding: `7px 14px`, font-size: 13px, color: `--muted`
- Hover: border-color → `--accent`, color → `--accent`, background → `rgba(200,245,66,0.06)`
- Transition: `all 0.2s`
- On click: fills the textarea with the chip text

### 5.4 Chat Bubbles

**User bubble (right-aligned):**
- Background: `#1e1e2e`, border: `1px solid #2e2e42`
- Border-radius: `18px`, bottom-right corner: `5px` (speech tail effect)
- Max-width: 82% of container

**Bot bubble (left-aligned):**
- Background: `--surface`, border: `1px solid --border`
- Border-radius: `18px`, bottom-left corner: `5px`
- Max-width: 82% of container
- Preceded by the bot avatar

**Bot Avatar:**
- 34×34px circle
- Background: `linear-gradient(135deg, --accent2, #a78bfa)`
- Text "FX" in Syne 700, 12px, white
- `flex-shrink: 0`, aligned to top of the bubble

### 5.5 Product Card
Rendered inside a bot bubble after a recommendation.

```
┌──────────────────────────────────┐
│  ⚡ BEST MATCH          (label)  │
│  Product Name           (Syne)   │
│  Why this solves your problem... │
│  [ View on Amazon ↗ ]   (CTA)   │
├──────────────────────────────────┤
│  Also consider: Alternative Name │
└──────────────────────────────────┘
```

- Outer wrapper: `--surface2`, `1px solid --border`, `border-radius: 14px`, `overflow: hidden`
- Inner padding: `16px`
- Label: `--accent`, 10px uppercase, letter-spacing 1.5px, font-weight 600
- Product name: Syne 700, 16px
- Why text: `--muted`, 13px, line-height 1.5
- "Also consider" strip: separate section separated by a `--border` top border, padding `12px 16px`, font-size 12px

### 5.6 CTA Button (View on Amazon)
- Background: `--accent` (`#c8f542`)
- Text color: `#0d0d0f` (dark, not white — high contrast on yellow-green)
- Font: Syne 700, 13px, letter-spacing 0.3px
- Shape: `border-radius: 100px` (pill), padding: `10px 18px`
- Icon: 13×13px arrow (↗) in SVG, stroke-width 2.5
- Hover: background → `#d4f760`, `translateY(-1px)`, box-shadow `0 4px 20px rgba(200,245,66,0.3)`
- Transition: `all 0.2s`

### 5.7 Typing Indicator
Three animated dots shown while the AI is processing.

- Three 7×7px circles, color `--muted`
- `blink` keyframe animation: opacity 0.2→1→0.2, scale 0.8→1.1→0.8
- Each dot offset by 0.2s delay
- Shown inside a standard bot bubble with avatar

### 5.8 Input Box
- Wrapper: `--surface`, `1px solid --border`, `border-radius: 18px`, padding `10px 10px 10px 18px`
- Focus state: border-color → `--accent2`, box-shadow `0 0 0 3px rgba(123,92,240,0.12)`
- Transition: `border-color 0.2s`
- Textarea: transparent background, `--text` color, DM Sans 14.5px, no outline, auto-resize up to 120px height
- Placeholder: `--muted`

### 5.9 Send Button
- 40×40px, `border-radius: 12px`
- Background: `--accent`, icon color: `#0d0d0f`
- Icon: upward arrow SVG, stroke-width 2.5
- Hover: background → `#d4f760`, `scale(1.05)`
- Disabled: background → `--border`, cursor not-allowed, icon → `--muted`
- Transition: `all 0.2s`

---

## 6. Animations

### `fadeUp` — Entry animation for all new elements
```css
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
/* Usage: animation: fadeUp 0.35s ease both; */
```
Apply to: every new chat message, intro card

### `pulse` — Logo dot heartbeat
```css
@keyframes pulse {
  0%, 100% { transform: scale(1);   opacity: 1;   }
  50%       { transform: scale(1.3); opacity: 0.7; }
}
/* Usage: animation: pulse 2.4s ease-in-out infinite; */
```

### `blink` — Typing indicator dots
```css
@keyframes blink {
  0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
  40%           { opacity: 1;   transform: scale(1.1); }
}
/* Delays: span:nth-child(2) → 0.2s, span:nth-child(3) → 0.4s */
```

### Scroll behavior
New messages scroll into view with:
```js
element.scrollIntoView({ behavior: 'smooth', block: 'end' });
```

---

## 7. Atmospheric Background Effects

Two pseudo-element glows on `body`, `position: fixed`, `pointer-events: none`, `z-index: 0`:

**Top glow (purple):**
```css
body::before {
  top: -200px; left: 50%; transform: translateX(-50%);
  width: 700px; height: 700px;
  background: radial-gradient(circle, rgba(123,92,240,0.12) 0%, transparent 65%);
}
```

**Bottom-right glow (green):**
```css
body::after {
  bottom: -100px; right: -100px;
  width: 400px; height: 400px;
  background: radial-gradient(circle, rgba(200,245,66,0.07) 0%, transparent 70%);
}
```

All content sits on `z-index: 1` above these.

---

## 8. Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>720px) | Content centered, max-width 720px, atmospheric glows visible |
| Tablet (480–720px) | Full width with `16px` side padding, glows still visible |
| Mobile (<480px) | Full width, chips wrap naturally, bubbles use 90% max-width |

No media queries needed for the current single-column layout — it is naturally fluid. The `max-width: 720px` constraint handles desktop centering.

---

## 9. Interaction States

| Element | Default | Hover | Focus | Disabled |
|---|---|---|---|---|
| Chip | `--muted` text, `--border` border | `--accent` text + border, green tint bg | — | — |
| CTA Button | `--accent` bg | lighter green, lift shadow | — | — |
| Send Button | `--accent` bg | lighter green, scale up | — | `--border` bg, `--muted` icon |
| Input Box | `--border` border | — | `--accent2` border + purple glow | — |
| Links | `#5a5a72` | underline | — | — |

---

## 10. Copy & Tone

### Header
- **Logo:** `Fixr`
- **Tagline:** `AI Product Finder` (uppercase, `--muted`, 12px, letter-spacing 0.5px)

### Intro Card
- **Headline line 1:** `Describe your problem.`
- **Headline line 2 (in `--accent`):** `Get the perfect product.`
- **Body:** `Tell me what's bothering you, what you need to fix, or what you're trying to accomplish — I'll find exactly what to buy.`

### Example Chips (starters)
- `My back hurts when I work from home`
- `I can't sleep because of noise`
- `My coffee goes cold too fast`
- `I keep losing my keys`
- `My phone dies halfway through the day`

### Product Card Label
- `⚡ Best Match`

### Disclaimer
- `Links may be affiliate links — I earn a small commission if you buy.` + `Learn more` link

---

## 11. File Structure Reference

```
product-finder/
├── index.html          ← Single-file frontend (all CSS + JS inline)
│
└── (backend)
    ├── main.py
    ├── config.py
    ├── models.py
    ├── requirements.txt
    ├── .env
    ├── routes/
    │   ├── chat.py
    │   └── health.py
    └── services/
        ├── ai_service.py
        └── affiliate_service.py
```

The frontend is intentionally a **single HTML file** — no build tools, no npm, no bundler. Open it in a browser and it works. Deploy it by dropping it on Vercel, Netlify, or any static host.

---

## 12. Future Design Extensions

These are not built yet but are consistent with the Fixr aesthetic:

| Feature | Design Direction |
|---|---|
| Multi-product comparison view | Horizontal card row inside a bot bubble, same card style, smaller |
| Price range filter chips | Same chip style as example chips, appear after first recommendation |
| "Save this product" button | Ghost button alongside the CTA, `--border` bg, saves to localStorage |
| Dark/light mode toggle | Header icon — light mode uses `#f5f5f0` bg with `#0d0d0f` text, `--accent` stays |
| Loading skeleton | Pulsing `--border`-colored rectangles matching card layout |
| Category badges | Small pill tags: `--surface2` bg, `--muted` text, on product name line |
