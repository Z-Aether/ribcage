// PROTOTYPE — ticket #9. Generates data.js from tmp/vote-films.json (TMDB + DTDD
// payloads fetched locally with the keys in docs/credentials, never committed).
// 32 real candidates (#19's shortlist, same set as the #24 prototype), nine voters,
// notes, other people's live vetoes, and one voter's own half-finished ballot.
// Run: node prototypes/voting-interface/gen-data.mjs
import { readFileSync, writeFileSync } from "node:fs";
const raw = JSON.parse(readFileSync("tmp/vote-films.json", "utf8"));
const voters = ["Ana", "Bence", "Csilla", "Dani", "Eszter", "Feri", "Gergő", "Hanna", "Iván"];
const ME = "Dani";
let s = 20260917; const rnd = () => (s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
const pitches = {
  "Evil Dead": ["Bence", "The 2013 one. Cabin, book, chainsaw. No jokes, all blood — the honest remake."],
  "The Wolf House": ["Eszter", "Stop-motion Chilean nightmare, 74 minutes. Every frame is a painting being eaten. Nothing else on this list looks like it."],
  "Infested / Vermines": ["Feri", "French spiders-in-a-tower-block. Genuinely tense and the building is a character."],
  "Weapons": ["Gergő", "Everyone is talking about it and I want to be in the room when the last act lands."],
  "Bring Her Back": ["Dani", "The Talk to Me brothers, meaner. Sally Hawkins is terrifying."],
  "Triangle": ["Csilla", "Loop film on a yacht. Best watched knowing nothing — please don't look it up."],
  "Final Destination Bloodlines": ["Feri", "The best one since the second. Rube Goldberg deaths, big laughs."],
  "28 Days Later": ["Bence", "Still the fastest zombies. Empty London is the scene."],
  "PG: Psycho Goreman": ["Ana", "A little girl enslaves a cosmic warlord. Very silly, very gory, pure joy."],
  "Willy's Wonderland": ["Hanna", "Nic Cage does not say a single word. That is the pitch."],
  "Time Lapse": ["Iván", "Camera that photographs tomorrow. Small, clever, cheap."],
  "Nightbreed (directors cut)": ["Gergő", "Clive Barker's monster city. The director's cut finally makes sense of it."],
  "Winnie-the-Pooh: Blood and Honey 2": ["Feri", "Hear me out: the sequel is actually competent. Ironic pick for the 2 a.m. slot."],
  "ThanksKilling": ["Ana", "A killer turkey. 67 minutes. You know what this is."],
  "The Blob": ["Bence", "1988 remake, practical goo effects, a kid dies in the first act. Bold for its time."],
  "Goodnight Mommy": ["Eszter", "Austrian twins, mother in bandages. Slow and then very much not."],
  "Slaxx": ["Hanna", "Possessed jeans in a fast-fashion store. Smarter than it sounds, still 77 minutes."],
  "Arachnophobia": ["Csilla", "Comfort horror. Jeff Daniels vs spiders, John Goodman as the exterminator."],
  "Death Becomes Her": ["Ana", "Not strictly horror but Streep and Hawn as immortal rivals is the campiest thing ever made."],
  "Longlegs": ["Dani", "Nic Cage again but you won't recognise him. The dread is the point, don't expect a twist."],
  "Late Night with the Devil": ["Csilla", "A 1977 talk show goes wrong on air. Found-footage that actually earns it."],
  "Terrifier": ["Feri", "Art the Clown. It's a lot. If we do it, we do it late."],
  "The Shining": ["Eszter", "The one everyone claims to have seen and half of us haven't."],
  "When Evil Lurks": ["Gergő", "Argentinian possession film with zero mercy. The dog scene is the one people warn about."],
  "In a Violent Nature": ["Gergő", "Slasher from the killer's point of view. Long walks through the woods, then not."],
  "The Thing": ["Bence", "Carpenter. The paranoia is the film — first slot while everyone can still follow it."],
  "The Exorcist": ["Dani", "The 4K restoration. I want to see if it still works on a room that has seen everything."],
  "Coco": ["Hanna", "Palate cleanser. Day of the Dead, everybody cries, then we go back to the gore."],
  "Phil Tippet's Mad God": ["Eszter", "Thirty years of stop-motion by the man who built the AT-ATs. Wordless. 60 minutes."],
  "Cube": ["Iván", "Six strangers, a cube of death traps, 1997 Canadian budget. Aged fine."],
  "Werewolf by Night": ["Ana", "Marvel did a black-and-white Universal monster homage and it's 55 minutes. Filler with teeth."],
  "Midsommar": ["Csilla", "Daylight horror, 147 minutes. Long, I know. Put it first and nobody has to leave in the dark."],
};
const extraNotes = {
  "The Thing": { Hanna: "Heavy strobe in the last twenty minutes — not a DTDD topic, but I know two of us mind it.", Ana: "In. Obviously." },
  "Midsommar": { Bence: "147 is a fifth of the whole budget. Just saying.", Dani: "Seen it twice and would go again if it's early." },
  "Late Night with the Devil": { Hanna: "Fair warning: 30–40 seconds of jittery static and strobe when the possession kicks off, plus a lot of vomiting, which DTDD does list." },
  "Terrifier": { Eszter: "I'm out for this one. Not a judgement, I just won't sit through it.", Ana: "Same. Watched ten minutes once." },
  "Coco": { Bence: "I refuse. It's a horror marathon.", Csilla: "It's a *film* marathon and it has skeletons." },
  "The Exorcist": { Csilla: "Sorry, this one is a hard no for me for personal reasons.", Gergő: "The restoration is gorgeous. Worth the big screen." },
  "Winnie-the-Pooh: Blood and Honey 2": { Dani: "No. We lost an hour to the first one." },
  "Weapons": { Csilla: "Please no spoilers in the notes. I've avoided everything." },
  "Cube": { Feri: "Runtime on TMDB says 90 but our copy is the 88 min cut, edited it." },
};
const suggester = Object.fromEntries(Object.entries(pitches).map(([t, [who]]) => [t, who]));
const films = raw.map(f => {
  const topics = (f.dtdd ? f.dtdd.topics : []).filter(t => t.yes + t.no >= 3).sort((a, b) => b.yes - a.yes);
  const notes = {}; const p = pitches[f.title]; if (p) notes[p[0]] = p[1];
  Object.assign(notes, extraNotes[f.title] || {});
  return { id: f.id, title: f.title, year: f.year, runtime: f.runtime, cert: f.cert, poster: f.poster, director: f.director, trailer: f.trailer, imdb: f.imdb,
    suggester: suggester[f.title] || "Iván", notes, dtdd: f.dtdd ? { id: f.dtdd.id, name: f.dtdd.name, year: f.dtdd.year, topics } : null };
});
const byTitle = t => films.find(f => f.title === t).id;
// other voters' vetoes — live, attributed (#10, #8)
const vetoes = {
  Eszter: { [byTitle("Terrifier")]: "not sitting through this one", [byTitle("In a Violent Nature")]: "" },
  Csilla: { [byTitle("The Exorcist")]: "personal reasons" },
  Bence: { [byTitle("Coco")]: "it's a horror marathon" },
  Ana: { [byTitle("Terrifier")]: "" },
};
// my own half-finished ballot — the "leave and resume" state
const half = { scores: {}, veto: {}, seen: {} };
const halfScores = { "The Thing": 3, "The Wolf House": 3, "Midsommar": 2, "Longlegs": 2, "Bring Her Back": 2, "Goodnight Mommy": 1, "Late Night with the Devil": 1, "Weapons": 1, "Triangle": 0, "Cube": 0, "Evil Dead": 0, "ThanksKilling": -1, "Slaxx": -1 };
for (const [t, v] of Object.entries(halfScores)) half.scores[byTitle(t)] = v;
half.veto[byTitle("Winnie-the-Pooh: Blood and Honey 2")] = "we lost an hour to the first one";
half.seen[byTitle("Midsommar")] = true; half.seen[byTitle("The Shining")] = true; half.seen[byTitle("The Exorcist")] = true;
// a full ballot, for the "everything scored" state
const full = { scores: {}, veto: { ...half.veto }, seen: { ...half.seen } };
for (const f of films) full.scores[f.id] = half.scores[f.id] ?? Math.max(-1, Math.min(3, Math.round(rnd() * 4 - 0.5)));
delete full.scores[byTitle("Winnie-the-Pooh: Blood and Honey 2")];
const watched = ["Does the dog die", "Are there flashing lights or images", "Are there spiders", "Does someone vomit"];
const done = ["Ana", "Feri", "Hanna"];
writeFileSync(new URL("./data.js", import.meta.url), "// generated by gen-data.mjs — PROTOTYPE #9\nwindow.DATA = " + JSON.stringify({ me: ME, voters, films, vetoes, watched, done, ballots: { fresh: { scores: {}, veto: {}, seen: {} }, half, full } }) + ";\n");
console.log(films.length, "films;", films.filter(f => f.dtdd).length, "with DTDD");
