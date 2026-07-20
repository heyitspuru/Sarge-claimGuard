# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** ClaimGuard
**Generated:** 2026-07-17 17:02:28
**Category:** Analytics Dashboard
**Design Dials:** Density 8/10 (Dense / Dashboard)

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#F0225F` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#C11A4C` | `--color-secondary` |
| Accent/CTA | `#F0225F` | `--color-accent` |
| Background | `#DBD7D8` | `--color-background` |
| Foreground | `#2B2528` | `--color-foreground` |
| Muted | `#CFC9CB` | `--color-muted` |
| Border | `#C4BEC0` | `--color-border` |
| Destructive | `#B91C1C` | `--color-destructive` |
| Ring | `#F0225F` | `--color-ring` |

**Color Notes:** Warm off-white base + vivid pink for every interactive element (buttons, links, active states, focus rings). Contrast: `#F0225F` on `#DBD7D8` ≈ 3:1 — fine for buttons/large UI, never for body text; body text is always `#2B2528` (≈11:1). White on `#F0225F` ≈ 4.1:1 — button labels must be ≥16px semibold. Hover states use `#C11A4C`.

### Typography

- **UI Font:** DM Sans (headings, body, labels)
- **Accent Font:** Instrument Serif *italic* — accent words inside headings only (h-plain/h-accent pattern: "Compliance *Radar*", "*3 breaches* found"). Never for body text.
- **Data Font:** Fira Code (record ids, numbers, timelines, tabular data)
- **Micro-labels:** uppercase, wide-tracked (11px, tracking-wider, muted), DM Sans medium
- **Mood:** dashboard, data, analytics, precise — with an editorial accent
- **Google Fonts:** DM Sans + Instrument Serif + Fira Code

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=Instrument+Serif:ital@0;1&family=Fira+Code:wght@400;500;600;700&display=swap');
```

### Spacing Variables

*Density: 8/10 — Dense / Dashboard*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `2px` / `0.125rem` | Tight gaps |
| `--space-sm` | `4px` / `0.25rem` | Icon gaps, inline spacing |
| `--space-md` | `8px` / `0.5rem` | Standard padding |
| `--space-lg` | `12px` / `0.75rem` | Section padding |
| `--space-xl` | `16px` / `1rem` | Large gaps |
| `--space-2xl` | `24px` / `1.5rem` | Section margins |
| `--space-3xl` | `32px` / `2rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #F0225F;
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  background: #C11A4C;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #C11A4C;
  border: 2px solid #F0225F;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #FFFFFF; /* cards sit on the #DBD7D8 page background */
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #F0225F;
  outline: none;
  box-shadow: 0 0 0 3px #F0225F20;
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Background Effect (DotField)

Page background: flat `#DBD7D8` with the ReactBits DotField layer on top.

Install (Phase 3, after frontend scaffold): `npx shadcn@latest add @react-bits/DotField-TS-CSS` (TS variant — `allowJs` is off in the Vite app)

```jsx
<div style={{ width: '1080px', height: '1080px', position: 'relative' }}>
  <DotField
    dotRadius={2.5}
    dotSpacing={20}
    cursorRadius={100}
    cursorForce={0}
    bulgeOnly
    bulgeStrength={0}
    glowRadius={50}
    sparkle={false}
    waveAmplitude={0}
    gradientFrom="rgba(240, 34, 95, 0.35)"
    gradientTo="rgba(240, 122, 158, 0.25)"
    glowColor="#F2B9C9"
  />
</div>
```

Only the three colors changed from the user's original config (purple → pink family derived from `#F0225F`); all behavior props are kept exactly as provided. For full-page use, replace the fixed 1080px wrapper with `inset-0 absolute` behind the content layer, and keep the effect static (respects `prefers-reduced-motion` since force/wave/sparkle are already 0/off).

---

## Style Guidelines

**Style:** Data-Dense Dashboard

**Keywords:** Multiple charts/widgets, data tables, KPI cards, minimal padding, grid layout, space-efficient, maximum data visibility

**Best For:** Business intelligence dashboards, financial analytics, enterprise reporting, operational dashboards, data warehousing

**Key Effects:** Hover tooltips, chart zoom on click, row highlighting on hover, smooth filter animations, data loading spinners

### Page Pattern

**Pattern Name:** Real-Time / Operations Landing

- **Conversion Strategy:** For ops/security/iot products. Demo or sandbox link. Trust signals.
- **CTA Placement:** Primary CTA in nav + After metrics
- **Section Order:** 1. Hero (product + live preview or status), 2. Key metrics/indicators, 3. How it works, 4. CTA (Start trial / Contact)

---

## Anti-Patterns (Do NOT Use)

- ❌ Ornate design
- ❌ No filtering

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
