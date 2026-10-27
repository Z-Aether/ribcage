# Privacy policy

[Marathon name] is a web app a group of friends uses to plan and run one film marathon. It is rebuilt for each marathon, runs for a few weeks, and is torn down when the marathon ends. This page says what it keeps about you, who can see it, and when it is deleted.

## What the app holds about you

- **Your display name.** It is the only personal detail the app asks for. It asks for no email address, real name or phone number.
- **Your password,** stored only as a hash.
- **What you do in the app:** your suggestions, notes, scores, vetoes and "seen it" flags, and whether you are done voting. Each is bound to your display name.
- **Your watched list:** the topics you want to be told about when a film has them, such as an animal dying. It is the most sensitive thing the app holds.

A session cookie keeps you signed in, and a CSRF cookie protects the forms.

## Who can see it

- **The group** sees your suggestions, notes, vetoes and "seen it" flags under your display name, and whether you are done voting. Your scores are hidden from other voters until voting closes, and then everyone's scores are shown to the whole group, by name. Nothing you do is anonymous; "hidden" only ever means hidden from other voters.
- **Your watched list is shown to no one else,** the admin included. No page shows it, counts it or sums it up for the group.
- **The admin and the host can read the database.** The admin runs the marathon; the host is the friend whose server runs the app. Either of them could read everything stored, including your watched list and your scores before voting closes. If that is not acceptable to you, leave your watched list empty and open each film's full topic list instead.

## Where it is kept

All of it is kept in one database on the host's server, with a nightly backup; the last seven are kept. The developer may copy a backup to their own machine to test a restore.

Films are looked up at TMDB and DoesTheDogDie from the server. Those requests carry film titles and ids, never your name or your watched list: matching your watched list against a film happens inside the app.

Posters load in your browser straight from TMDB's image servers, so TMDB sees your IP address and which posters your browser loads, though not your name.

## Logs

The app logs the requests it serves, without your IP address.

The host's own proxy may log requests; those logs never contain what you flagged. The proxy sits in front of the app, and its logs, kept under the host's own retention, may include your IP address and the page requested. The topics on your watched list never appear in a web address.

## When it is deleted

Everything the app holds is deleted at teardown, at the end of each marathon: the database, its backups, the app's logs and the developer's copies.

The one exception is a pseudonymised score matrix the developer keeps privately for testing. It holds the scores, vetoes and "seen it" flags with display names replaced by numbered labels, and no watched lists.
