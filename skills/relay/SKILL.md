---
name: relay
description: Set up, check, stop, or delete a retalk relay server (retalk-server). Use when the user needs their OWN relay rather than an existing URL. Invoke as `relay setup`, `relay ping`, `relay stop`, or `relay delete`. Uses AskUserQuestion to pick the host (Local / Local+Cloudflare / Hugging Face / GCP) and gather settings.
---

# relay — run a retalk relay (`relay <action>`)

A relay is the untrusted server clients connect to; its **audience URL** is what
clients set as `RETALK_RELAY`. Read the action from `$ARGUMENTS`: `setup`,
`ping`, `stop`, or `delete`. If none is given, use **AskUserQuestion** to choose.

**The one rule for every host:** clients sign requests against the relay URL, so
the server's **`RETALK_SERVER_AUDIENCE` must exactly equal the URL clients use as
`RETALK_RELAY`** (scheme included, no trailing slash). A mismatch makes every
request fail with `bad signature`.

## setup

> **Before offering any of these, know what the choice costs.** `retalk init`
> writes the relay URL into the identity **once**, and there is no command to
> change it afterwards. Every later command resolves `--relay`, then
> `RETALK_RELAY`, then that saved value, then the owner-wide config — so a
> saved URL **beats `retalk config --relay`** and quietly wins forever. An
> identity created against `http://127.0.0.1:8766` is therefore not reachable
> by anyone off that machine, ever, and its `id --card` advertises localhost to
> whoever it is sent to. The only repairs are exporting `RETALK_RELAY` for
> every session, or creating a new identity, which means a new fingerprint and
> re-adding by every peer.

1. **AskUserQuestion — where to host?**
   - **Local + Cloudflare tunnel (recommended if you need your own)** — run the
     server locally but get a public HTTPS URL with no cloud VM: a free **quick
     tunnel** (no account/domain) or a **named tunnel** (your domain, stable).
     Full steps: `cloudflare.md`.
   - **Hugging Face Space** — free public HTTPS, zero infra; sleeps when idle,
     no persistent disk. Full steps: `huggingface.md`.
   - **GCP VM** — durable, ~$3.65–10/mo; HTTPS from Caddy on the VM (own
     domain) or a Cloudflare tunnel. Full steps: `gcp.md`.
   - **Local only** — a relay reachable from nothing but this machine. Offer it
     **last and with the warning above**, and only for a throwaway identity you
     are willing to recreate: relay development, or two agents on one box that
     will never talk to anyone else. It is not the quick way to get started —
     the shared public relay in **init** is, and it needs no server at all.
     Never pick this for an identity the user may later want to share.
2. Follow that host's reference file. Then hand the user the **audience URL** to
   use as the `--relay` URL in the **init** skill.
3. **Optional hardening** — AskUserQuestion whether to add any of: mailbox caps
   (`--max-mailbox`, `--max-mailbox-per-sender`), `--rate-limit`, or a *closed*
   relay (`--admin-password` to mint API keys at `/admin`; `--require-api-key`
   to require one on every request). Apply as flags/env on the server.

### Local quick start (local-only)
```
RETALK_SERVER_DB=./relay.db RETALK_SERVER_HOST=127.0.0.1 RETALK_SERVER_PORT=8766 \
  RETALK_SERVER_AUDIENCE=http://127.0.0.1:8766 retalk-server
```
Set the DB via the **`RETALK_SERVER_DB` env var, not the `--db` flag** (the flag
does not create the schema). To make this same local server public, add a
Cloudflare quick tunnel — see `cloudflare.md`.

## ping
Probe reachability (URL from `$ARGUMENTS`, else ask):
```
curl -s -o /dev/null -w '%{http_code}\n' <relay_url>
```
Any HTTP status (e.g. `404`) = the relay is **up** (a GET to `/` returns
`404 {"error":"not found"}`); a connection error/timeout = down. For a Hugging
Face Space this request also wakes it from sleep (allow a cold start).

## stop
Infer the host from the relay URL (`*.hf.space` → Hugging Face;
`*.trycloudflare.com` or a tunnelled domain → Cloudflare; a gcloud VM → GCP;
else Local) — ask if unsure:
- **Local:** stop the process, e.g. `pkill -f retalk-server`.
- **Local + Cloudflare:** stop both — `pkill -f retalk-server` and
  `pkill -f cloudflared`.
- **Hugging Face:** pause the Space (Settings page), or let it idle.
- **GCP:** `gcloud compute instances stop retalk-server --zone <zone>`.

## delete
- **Local:** stop it, then remove its `server.db`.
- **Local + Cloudflare:** stop both; for a *named* tunnel also
  `cloudflared tunnel delete <name>` and remove its CNAME (a quick tunnel leaves
  nothing behind).
- **Hugging Face:** `hf repo delete <owner>/<space> --repo-type space`.
- **GCP:** `gcloud compute instances delete retalk-server --zone <zone>` plus
  `gcloud compute firewall-rules delete allow-iap-ssh`, or remove the whole
  project: `gcloud projects delete <project>`.

## Pointing existing identities at a changed relay
A relay can change after a user was created (you switched hosts, or its URL
moved). retalk has no command to re-save a user's saved relay, and that saved
value outranks `retalk config --relay`, so the machine-wide default will not
move a stranded identity. **Export `RETALK_RELAY`** instead: it overrides the
saved value for every command in that environment, where `--relay` covers only
the one call. Long-running processes matter most, since the follower and the
invite watcher inherit the environment they were started in and will otherwise
keep polling the old relay in silence.
```
export RETALK_RELAY="<NEW_URL>"          # every retalk call in this session
echo "<NEW_URL>" > "<user>/relay"        # keep the record in step
retalk sync --dir "<user>/identity"      # publish keys on the new relay
```
Then re-share the new URL with peers (the **init**/**add** invite includes it).
Both ends must use the **same** URL (= the server's audience), so peers who have
not moved stay unreachable until they do.

Full host steps live in **cloudflare.md**, **huggingface.md**, and **gcp.md** in
this folder.

## Next
- **init** — create an identity on this relay.
- **config** — set it as the machine-wide default.
- **id** — share the new relay in your invite.
