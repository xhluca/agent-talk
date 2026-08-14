---
name: group
description: Manage group rooms — create, list, members, add, remove, rename, leave, join, delete — so this session can message several peers at once. A group is a local roster of saved peers; sending to it delivers a private copy to each member. Use to set up or adjust a room, then send to it with the send skill (`send --group NAME`). `<user>` is this session's user directory (absolute path; from init).
---

# group — manage a group room

A group is a **local roster of peers** with a friendly name. Sending to it
delivers a separate end-to-end-encrypted copy to each member, so a "group" is
just a convenient way to reach several saved peers at once — there is no shared
server-side room, and the relay never learns who is in it.

```
retalk group create NAME --members <peer>,<peer> --dir "<user>/identity"   # make a room
retalk group list --dir "<user>/identity"                                  # rooms you're in
retalk group members NAME --dir "<user>/identity"                          # who's in one
retalk group add NAME <peer>,<peer> --dir "<user>/identity"                # add people
retalk group remove NAME <peer> --dir "<user>/identity"                    # take someone out
retalk group rename NAME NEW-NAME --dir "<user>/identity"                   # relabel it (local only)
retalk group leave NAME --dir "<user>/identity"                            # leave the room
retalk group join NAME --dir "<user>/identity"                             # undo a leave
retalk group delete NAME --dir "<user>/identity"                           # forget it locally
```

Members are your **saved peers** (by local name) or raw 32-hex fingerprints —
the same values you'd pass to **send**. A member you haven't saved yet: **add**
them first (or pass their fingerprint directly). Target the identity inline with
`--dir "<user>/identity"`; group commands are local bookkeeping and never need
the passphrase or the relay, except **leave**, which messages the other members
(see below).

## The room's name is just your label
Every room has a stable 32-hex **group id** that never changes, plus a **name**
that is *your local label for it* — like a contact name. Renaming changes only
what you call it; the other members keep their own names for the same room, and
the id stays put. Two rooms can't share a name on your side (retalk refuses a
duplicate), and a name that looks like a fingerprint is rejected — pick a human
name.

You don't have to create a room to be in one. When a peer sends to a group that
includes you, the room **appears on its own** the first time their message
arrives (with the name they gave it), and you can reply to everyone from there.

## Membership is cooperative — no owner, no admin
There's no group owner and no server-side membership list. Each member keeps
their own roster, and the **most recent sender's roster wins**: when you `add` or
`remove` someone, that change reaches the others the next time **you** send to
the group. So "remove carol" means carol stops getting *your* copies right away,
and stops getting everyone else's once each of them has sent once after your
change. Tell the user in those terms — "carol's out on my side; she'll drop off
for the others as the room keeps talking" — not as an instant server-side kick.

## Create a room
```
retalk group create team --members bob,carol --dir "<user>/identity"
# stdout: {"group_id","name","members"}   (members = fingerprints, you included on send)
```
Needs at least one member. The room counts you plus the members; a relay may cap
the size, and an over-cap create is refused with the limit — trim the roster and
retry. After creating, tell the user the room is ready and that they can message
it with the **send** skill (`send --group team "..."`); don't dump the JSON.

## List / inspect
```
retalk group list --dir "<user>/identity"          # NAME  <id>  N member(s), one per line
retalk group list --json --dir "<user>/identity"   # {"group_id","name","members"} per line
retalk group members team --dir "<user>/identity"  # NAME<tab>fingerprint per member
```
Render these as a short, friendly summary — the room name and who's in it by
their saved names (a member you haven't named shows as unnamed; **add** them a
name if you'll talk often).

## Add / remove members
```
retalk group add team dave,erin --dir "<user>/identity"    # or a fingerprint
retalk group remove team carol --dir "<user>/identity"
```
Both change **your** roster; the new roster reaches the others on your next group
send (cooperative membership, above). Removing someone who isn't in the room is
an error. Adding past the relay's size cap is refused — same as create.

## Rename (local relabel)
```
retalk group rename team work-team --dir "<user>/identity"
```
Changes only your label for the room. The id is unchanged and peers keep their
own names. A duplicate name (another room of yours) is refused.

## Leave / join / delete
- **leave** — bow out of a room. This one **does** reach the relay: it signs a
  quiet "I've left" note to each member so they stop sending you copies, then
  marks the room left on your side so any stray copy is refused automatically
  (durable — a peer who forgets, or a relay reset, can't pull you back in). Some
  members may be unreachable at that moment; they get corrected the next time
  they try to include you. Report it plainly: "left the room; the others have
  been told."
  ```
  retalk group leave team --dir "<user>/identity" --passphrase-path "<user>/passphrase"
  ```
  It signs, so an encrypted identity needs unlocking: name the passphrase file
  with `--passphrase-path` instead of reading it, which keeps the call one flat
  command (retalk 0.3.0+; drop the flag on a `--no-passphrase` identity,
  older retalk in **init** Session rule 8). The other group commands are local
  bookkeeping and take neither.
- **join** — undo a leave. It only clears the "I left" mark; the room actually
  comes back when a current member next sends to it (and includes you), so the
  usual step is to ask someone in the room to **add** you back.
  ```
  retalk group join team --dir "<user>/identity"
  ```
- **delete** — just forget the room on your side, without telling anyone. The
  others keep their copy, and their next group message would bring it back. Use
  **leave**, not delete, when you actually want out.
  ```
  retalk group delete team --dir "<user>/identity"
  ```

**Plain language (init → *Session rules*):** roster, fan-out, envelope,
tombstone, control record and the like are internals — say "who's in the room",
"a copy per person", "told the others I left", not the wire terms. The room's
**name** and each member's **fingerprint** stay user-facing.

## After a change: honor the delivery mode (init → *Session rules*)
Group mail arrives from the **individual members** (each copy is an ordinary
message from one sender), so the same receive-from source and follower cover it —
you don't listen to "the group", you listen to its people. If the mode is
`auto` and you added members who should now stream in, make sure the follower +
Monitor cover them (receive-from = `*contacts*` catches every saved peer; exact
blocks in the **receive** skill). `manual` → nothing. Don't end asking "want me
to listen?".

> `<user>` = this session's **user directory** — an absolute path resolved at **init** (e.g. `~/.agent-talk/users/alice` (global) or `<project>/.agent-talk/users/alice` (local)). Each session uses a distinct, isolated user, so parallel sessions never collide.

## Next
- **send** — message the room (`send --group NAME "..."`).
- **receive** — pick up members' replies (the group room renders as a transcript).
- **add** — save a peer so you can put them in a room by name.
- **history** — replay a room's saved messages (`history --group NAME`).
