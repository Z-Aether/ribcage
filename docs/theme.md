# The theme

How Ribcage looks, and why, for anyone building a new surface (#58). The values live in `ribcage/static/theme/theme.css`. The visual reference is the **gallery**: with `DEBUG` on, open `/gallery/` on the seeded instance. Directions A (neon orange) and C (peat and bone) were worked out and set aside; they are kept on the local branch `prototype/theme`.

## The feel

The marathons are horror marathons, watched in a dark room. The theme is dark only: there is no light theme. It aims for cosy Halloween, a lantern in a dark kitchen, rather than a party-supply shop: warm aubergine and pumpkin, soft contrast that is easy on the eyes, and playful details such as a bat, a spider and hand-cut corners. It should never look like a generic template, so don't reach for system fonts, gradients over everything, glass panels, emoji icons or the same drop shadow on every card.

## Skins

A page wears the voter skin unless it names admin or run in base.html's `skin` block, which sets `data-skin` on `<body>`. A section may set its own.

- **voter**: rounded, roomy and uncluttered, with bigger values and no hint text. This is where the play lives.
- **admin**: dense, plain ledgers with one row per item. No decoration, no motion and no mist.
- **run**: the voter's evening, darker still, because the room is dark.

## Tokens that matter

- **Ground and ink:** ground `#1b1420`, surface `#241b2b`, raised `#2c2134`, lines `#3a2d44` and `#56456a`. Ink `#eadccb` and muted ink `#b8a6b4`, both warm off-whites rather than dimmed text.
- **Accent:** pumpkin `#ef8a3f`, for primary buttons (a link wears one as `a.button`), the wordmark and the pitch. Plum `#9a74c8` frames the open card, and lilac `#c9a6f0` is for links and the focus ring every control shows.
- **State colours**, shared by every later surface:
  - the score scale: sea-glass for wanting it, +3 Top pick `#7dd3c0`, +2 Keen `#4aa292`, +1 Happy `#2e6a62`; grey for 0 Don't mind `#43384b`; dusty rose for −1 Rather not `#dca0b6`;
  - the **veto**: a dashed red border, `#ff6363`, unlike any score;
  - the **trigger icon**: a lime ring, `#b9e46e`, on a tile's frame;
  - **seen it**: the poster greyed and dimmed. It is the only filter a poster ever gets: every other poster keeps its own colours.
- **Title card fill:** the one muted fill is `#3b2647`, with the title in `#f6d9b8`.
- **Type:**
  - Mystery Quest for display: headings, card titles, the wordmark and title cards. It is bouncy and spooky but legible.
  - Alegreya Sans for body text and labels, chosen for reading.
  - Fraunces italic for **notes**, so the group's own words read as handwritten and warm, apart from the app's voice.
  - Admin uses Alegreya Sans throughout.
- **Shape:** voter corners are hand-cut, no two alike, like a carved pumpkin. The pitch sits under a jagged sliver of pumpkin. Admin corners are small and regular.

## Motion

Motion is slow and small, and it is never on the text.

- **Mist:** a lilac and ember mist drifts behind every voter and RUN page over 90 s.
- **Bat:** it roosts by the wordmark and takes off every 9 s, the theme's one jump scare.
- **Spider:** it bobs below the open **film card**'s poster.
- **Hover:** collapsed cards tilt, and buttons and score pills wobble.
- **RUN:** the now-playing box breathes like a candle over 4.3 s.
- **Tuning:** the bat and spider get their final tuning in M4.
- **Reduced motion:** under `prefers-reduced-motion` everything stands still.
- **Admin:** nothing moves on admin.

## Adding a colour

A new colour must stay distinct from every state colour above and from the pumpkin, plum and lilac, so that no state reads as the accent. Body text keeps WCAG AA against its ground; soften with warm off-blacks and off-whites, never with dim text. Ink measures 13.4:1 on the ground and muted ink 6.7:1 on raised. Texture and mist sit behind text, never on it.
