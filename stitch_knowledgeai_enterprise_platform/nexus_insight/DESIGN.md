# The Design System: Editorial Intelligence

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Intelligent Curator."** 

In an era of information overload, this system moves away from the "cluttered dashboard" trope of legacy enterprise software. Instead, it adopts a high-end editorial aesthetic. We treat knowledge as a premium asset. By utilizing intentional asymmetry, expansive breathing room, and a sophisticated layering strategy, we transform a data-heavy platform into a serene, authoritative workspace. The goal is "invisible infrastructure"—where the interface recedes to let the user’s knowledge take center stage.

---

## 2. Color & Tonal Architecture
We utilize a sophisticated palette that balances high-trust blues with deep, structural neutrals.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to section off the layout. Structural boundaries must be defined exclusively through background color shifts or tonal transitions. For example, a `surface-container-low` navigation panel should sit flush against a `surface` main content area. The eye should perceive the edge through the shift in value, not a rigid line.

### Surface Hierarchy & Nesting
The UI is not a flat grid; it is a series of stacked physical layers. 
- **Surface (Background):** The base canvas (`#f9f9ff`).
- **Surface-Container-Low:** Secondary utility areas or "wells."
- **Surface-Container-Lowest:** High-priority content cards (`#ffffff`).
- **Surface-Container-Highest:** Active overlays or "pop-outs."

### The "Glass & Gradient" Rule
To avoid the "out-of-the-box" SaaS look, use **Glassmorphism** for floating elements (e.g., Command Palettes or Tooltips). Apply `surface-container-low` with a 70% opacity and a `backdrop-blur` of 12px. For primary CTAs, use a subtle linear gradient from `primary` (#003fb1) to `primary_container` (#1a56db) at a 135-degree angle to add "soul" and depth to buttons.

---

## 3. Typography: The Editorial Voice
We use **Inter** for its modern clarity and **JetBrains Mono** for technical precision. 

- **Display & Headline:** Used sparingly to create "Moments of Impact." These should utilize significant bottom margins (32px+) to allow the brand's authority to breathe.
- **Title (SM/MD/LG):** These serve as the functional anchors for blocks of knowledge.
- **Body (MD):** Our workhorse. 14px (0.875rem) with a generous 1.5 line-height ensures high-velocity reading.
- **Label:** Used for metadata. These should often be set in `on_surface_variant` (#434654) to maintain the visual hierarchy.

*Design Note:* The high contrast between `display-lg` and `body-md` is what creates the "Editorial" feel. Do not be afraid of large type next to small, dense data.

---

## 4. Elevation & Depth
Hierarchy is achieved through **Tonal Layering** rather than structural shadows.

- **The Layering Principle:** Place a `surface-container-lowest` card on a `surface-container-low` section to create a soft, natural lift.
- **Ambient Shadows:** When an element *must* float (e.g., a dropdown), use an extra-diffused shadow: `box-shadow: 0 10px 40px rgba(0, 63, 177, 0.06)`. Note the tint—the shadow color is a faint version of the `primary` blue, mimicking natural light.
- **The "Ghost Border" Fallback:** If a container lacks contrast against its background, use a **Ghost Border**: 1px solid `outline_variant` at **15% opacity**. Never use 100% opaque borders.

---

## 5. Components

### Buttons & Inputs
- **Primary Action:** Solid gradient (`primary` to `primary_container`), 8px (`DEFAULT`) radius. High-trust, high-impact.
- **Secondary Action:** Ghost-style (no fill) with a `primary` text label. 
- **Inputs:** `surface-container-lowest` fill. On focus, the border transitions to `primary` with a 3px "halo" of `primary_fixed` at 50% opacity.

### Knowledge Cards & Lists
- **The Divider Rule:** Forbid 1px horizontal dividers. Separate list items using 12px of vertical white space or a subtle hover state shift to `surface-container-low`.
- **Cards:** 12px (`md`) radius. Content should be padded with a minimum of 24px to maintain the "Editorial" breathing room.

### Navigation (The Dual-Tone Sidebar)
- **Chat Sidebar:** Use `inverse_surface` (#263143). This creates a focused "dark mode" zone for intense AI interaction.
- **Admin Navigation:** Use `surface_container_low`. A lighter, utility-focused zone for management tasks.

### Additional Signature Components
- **The "Focus Node":** A semi-transparent chip used for AI-generated tags, utilizing `primary_fixed` backgrounds with `on_primary_fixed_variant` text.
- **The Breadcrumb Trail:** Minimalist typography (label-md) using `outline` for separators, avoiding chevrons to keep the interface clean.

---

## 6. Do’s and Don’ts

### Do
- **Use White Space as a Tool:** Treat empty space as an active element that guides the user's eye.
- **Layer with Intent:** Ensure that inner containers are always a different tonal tier than their parent container.
- **Respect the Radius Scale:** Use 16px (`xl`) for large message bubbles and 8px (`DEFAULT`) for functional components like buttons.

### Don’t
- **Don’t use 100% Black:** Always use `on_surface` (#111c2d) for primary text to avoid harsh optical vibration.
- **Don’t Over-Shadow:** If you can define a section with a color shift, do not use a shadow.
- **Don’t Box Everything In:** Avoid the "Table View" look. Let data breathe without being trapped in rigid cells and borders.