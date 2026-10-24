# The theme

How Ribcage looks, and why, for anyone building a new surface (#58). The values live in `ribcage/static/theme/theme.css`. The visual reference is the **gallery**: with `DEBUG` on, open `/gallery/` on the seeded instance. Directions A (neon orange) and C (peat and bone) were worked out and set aside; they are kept on the local branch `prototype/theme`.

## The feel

The marathons are horror marathons, watched in a dark room. The theme is dark only: there is no light theme. It aims for cosy Halloween, a lantern in a dark kitchen, rather than a party-supply shop: warm aubergine and pumpkin, soft contrast that is easy on the eyes, and playful details such as a bat, a spider and hand-cut corners. It should never look like a generic template, so don't reach for system fonts, gradients over everything, glass panels, emoji icons or the same drop shadow on every card.

## Skins

A page wears the voter skin unless it names admin or run in base.html's `skin` block, which sets `data-skin` on `<body>`. A section may set its own.

- **voter**: rounded, roomy and uncluttered, with bigger values and no hint text. This is where the play lives.
- **admin**: dense, plain ledgers with one row per item. No decoration, no motion and no mist.
  - An act that asks first is a click and then an inline confirm. *Cancel* takes the clicked button's place at its size (`console/cancel.html`), and the button naming the act stands apart, at the start of a line after what the act does. The tab keeps its scroll across the click and Cancel, and from a reset's confirm onto the password it shows, through a `data-keeps-scroll` region round its arms and confirms, so Cancel comes up under the pointer and the password in view (#85). An act that asks nothing, as *Approve* and *Drop* on the Films tab, is a plain button that reloads the tab where it was, its form naming the page it lands on in `data-lands-on`. Its row, marked `data-keeps-place`, comes back at the same height on screen though the reload closes any open card above it, and the ledger keeps its sideways scroll, so at 390 px the acts stay in view decision after decision; a row the decision takes out of the filter leaves the row after it where it was (#96). The Films tab's runtime box is a small box of minutes on its row's line, its source tag after it, or *required to approve* in the veto's ink when empty, then *⚠ TMDB says 144* in pumpkin while it differs from TMDB's, and a quiet *Save*. A refusal takes a line of its own under the box, in the note box's rose, with the typed value kept and focused (#97).
- **run**: the voter's evening, darker still, because the room is dark.

## Tokens that matter

- **Ground and ink:** ground `#1b1420`, surface `#241b2b`, raised `#2c2134`, lines `#3a2d44` and `#56456a`. Ink `#eadccb` and muted ink `#b8a6b4`, both warm off-whites rather than dimmed text.
- **Accent:** pumpkin `#ef8a3f`, for primary buttons (a link wears one as `a.button`), the wordmark and the pitch. Plum `#9a74c8` frames the open card, and lilac `#c9a6f0` is for links and the focus ring every control shows.
- **State colours**, shared by every later surface:
  - the score scale: sea-glass for wanting it, +3 Top pick `#7dd3c0`, +2 Keen `#4aa292`, +1 Happy `#2e6a62`; grey for 0 Don't mind `#43384b`; dusty rose for −1 Rather not `#dca0b6`;
  - the **veto**: a dashed red border, `#ff6363`, unlike any score;
  - the **trigger icon**: a lime ring, `#b9e46e`, on a tile's frame;
  - **seen it**: the poster greyed and dimmed. It is the only filter a poster ever gets: every other poster keeps its own colours.
  - The password confirmation's live line borrows two of them, sea-glass when the passwords match and rose when they differ, since no score shows beside it (#72).
- **Title card fill:** the one muted fill is `#3b2647`, with the title in `#f6d9b8`.
- **Type:**
  - Mystery Quest for display: headings, card titles, the wordmark and title cards. It is bouncy and spooky but legible.
  - Alegreya Sans for body text and labels, chosen for reading.
  - Fraunces italic for **notes**, so the group's own words read as handwritten and warm, apart from the app's voice. A voter writes their own in the same hand, in the note box (#88).
  - Admin uses Alegreya Sans throughout.
- **Shape:** voter corners are hand-cut, no two alike, like a carved pumpkin. The pitch sits under a jagged sliver of pumpkin. Admin corners are small and regular.

## Phase bars

A **phase bar** is the foot of an opened film card, where a voter acts on it, and the one part of the card that changes between surfaces. It sits under a dashed line, in a row of its own beside the poster, and takes the card's whole width on a phone. SUGGEST's and APPROVE's hold the **note box**: a label, *Your pitch* in pumpkin on your own suggestion and *Your note* on the rest, a box with no placeholder or hint, and *Save*. An opened card leaves the voter's own note out of its list, since the box holds it, and a closed card lists it (#88). Its line beside *Save* says *Saved.* or *Cleared.*, or gives a refusal kindly, in the dusty rose the password confirmation borrows. It has no `maxlength`, since a browser cuts a long paste silently; the server refuses it whole instead (#88). On your own card while it can be withdrawn, SUGGEST's bar ends Save's line with a quiet *Withdraw…*. It asks first, as the console's acts do: *Cancel* takes its place at its size, and below come what goes with the film and the pumpkin button naming it, at the start of a line of its own. A withdrawn card fades as it leaves the pool (#85, #89).

## The pool filter

*Everyone's* and *Mine* sit above the pool as two pills, the chosen one in pumpkin and the other quiet, with the choice exposed as `aria-pressed`. They show only once their script has run, so without script the whole pool shows. An empty *Mine* says *You haven't suggested any films.* in the body voice, and the pool's own empty line stays hidden then (#91).

## The poster tile

A **tile** is a poster or its title card with the title and a muted year beneath, in `components/tile.html`; the caller frames it and sets its state classes. The picker's tiles add the original title where it differs, and are buttons that keep the tile's look: reached for, the poster lifts and takes a pumpkin edge. A film already in the pool says *already suggested by …* in pumpkin under its tile, naming its suggester, or *already suggested by you* on the searching voter's own (#92; the dev, 2026-10-23). M6's ballot tiles extend the same tile with the state colours below (#61, #92).

## The Suggest a film panel

The panel sits above the pool's filter on a surface of its own: the heading, one *Title* box, and the picker under it, five tiles in a row on a desktop and three to a row on a phone. TMDB finding nothing is one line in muted ink where the tiles would be, and TMDB not answering is the same, with *add it by hand* as a link at its end. Under the tiles one more muted line reads *None of these? Add the year or add it by hand.*, *Add the year* emphasised and not a link, and under the no-results line the by-hand offer stands alone as *Add it by hand.*; either way *add it by hand* is a link that swaps the hand step in, its *Title* box holding what was searched and its *Year* box any trailing year (#92, #94; the dev, 2026-10-23 and 2026-10-24).

The **pitch step** takes the picker's place: the poster beside the title, a muted year, the director and the certificate, then *Your pitch* in pumpkin over a large box in the notes' hand with the pitch's pumpkin edge, autofocused. Under it one quiet line reads *Runtime 144 min TMDB ✎*, whose pencil turns it into the runtime pencil's box of minutes, with no *Save* or *Cancel*, since *Add* takes what it holds. A refusal is a line of its own under its box, in the note box's dusty rose. *Add* is the pumpkin button at the start of the last line, disabled until the pitch and the runtime hold something (the dev, 2026-10-23). On a phone the pitch box and what follows take the step's whole width under the poster. The step for a film by hand has no poster: a title box and an optional year box take its place, and the rest follows the same way, with *Add* waiting on the title too (#93, #94; the dev, 2026-10-23).

## The runtime pencil

Where a voter may correct a film's runtime, the card's runtime line ends in a quiet ✎ in muted ink, which turns pumpkin and tips when reached for. A click turns the line into a small box of minutes with *Save* and a quiet *Cancel*, in place on an open or closed card alike. A refusal takes a line of its own beneath, in the note box's dusty rose, and the typed value stays in the box. Saved, the line shows the new runtime with its *by hand* tag, or *TMDB* again when it is corrected back to TMDB's value (#90).

## The DoesTheDogDie section

An opened film card's DoesTheDogDie section follows the notes, in a row of its own above the phase bar, and on a phone it takes the card's whole width; a collapsed card shows none of it. On the voter skin it sits on the plain surface, framed in the line colour with the controls' hand-cut corners, a step down from the raised open card; on admin it is a plain block under a thin line. It reads the same for every viewer and adds no colour of its own (#103).

- **The match line:** *DTDD:* in muted ink, the record's name and year as a link with ↗, then *· auto* or *· set by Ada* in muted ink.
- **A gap** is a muted line led by its word, *uncovered*, *not fetched* or *no match*, in a dashed muted pill, as the ledger names it, so nothing reads as a count or an all-clear. An uncovered film matched to an empty record keeps its match line above the gap.
- **The topic list** waits behind one lilac control, *All 42 topics on DoesTheDogDie*, with a chevron that turns as it opens. Each super-category is a small uppercase muted heading, and its rows are the topic in ink and *— 3 yes / 1 no* in muted tabular figures, in as many columns as the card has room for, one on a phone. Its rows arrive as it first opens, after a moment's muted *Fetching the topics…*, and stay open with it when a note is saved below.
- **The credit**, *Powered by DoesTheDogDie.com*, ends the section a little smaller, whenever it shows a match or topics.

## The Films tab

A line gives the ballot's size and screen time, then the four filters sit as small square-cornered links, the chosen one edged in pumpkin, each with its count in muted ink. The ledger's approval column is a small uppercase tag: *undecided* in pumpkin, *approved* in sea-glass, *dropped* in muted ink. A title is a bold plain button that opens the card in a row of its own beneath, one at a time; the card's own title closes it again. On a phone the directors give way, the ledger scrolls sideways within its own frame, and an opened card holds still at the frame's width (#95). Its columns keep fixed widths, so every filter lays out alike and only the film's column gives, and each row's poster is a thumbnail 1.5rem wide, small enough to keep the row dense and big enough to know the film. The row under the pointer, or holding keyboard focus, lifts to the raised surface, its opened card with it, so *Approve* and *Drop* are plainly on that film (the dev, 2026-10-24). The *DTDD* column, between the runtime and the approval, gives a matched film's topic count in ink, and names each gap, *uncovered*, *not fetched* or *no match*, in muted italic, so no gap reads as a count; one quiet *Powered by DoesTheDogDie.com* link sits under the ledger (#102).

## Motion

Motion is slow and small, and it is never on the text.

- **Mist:** a lilac and ember mist drifts behind every voter and RUN page over 90 s.
- **Bat:** it roosts by the wordmark, wings spread and still, and takes off at random, 12 to 30 s apart, as `components/bat.js` picks; on admin pages it only roosts. Each flight is the theme's one jump scare: a jolt off the roost that swells as if at you, then a wide loop out to the right and home over 2.6 s, its wings flapping all the way (#99).
- **Spider:** it hangs on its silk from the bottom edge of the open **film card**'s poster, poster or title card, and bounces: a drop, a spring back up the silk, a few smaller bounces, then a while hanging still. Only the silk's length moves, so its top never leaves the poster's edge (#99).
- **Hover:** collapsed cards tilt, and buttons and score pills wobble.
- **RUN:** the now-playing box breathes like a candle over 4.3 s.
- **Reduced motion:** under `prefers-reduced-motion` everything stands still.
- **Admin:** nothing moves on admin. The console's wordmark keeps its bat, roosting, and no admin card has a spider.

## Adding a colour

A new colour must stay distinct from every state colour above and from the pumpkin, plum and lilac, so that no state reads as the accent. Body text keeps WCAG AA against its ground; soften with warm off-blacks and off-whites, never with dim text. Ink measures 13.4:1 on the ground and muted ink 6.7:1 on raised. Texture and mist sit behind text, never on it.
