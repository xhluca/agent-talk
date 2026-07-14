# relay setup — Google Cloud VM (durable)

A small `e2-micro` VM runs `retalk-server`; its public HTTPS URL comes either
from **Caddy on the VM** (default when the user owns a domain: one A record at
the VM's static IP, automatic Let's Encrypt certs) or from a **Cloudflare
tunnel** (the VM keeps NO inbound ports open; no domain needed with a quick
tunnel). Roughly $3.65/mo (free-tier compute) up to ~$10/mo on-demand. Ask
(AskUserQuestion) for the project name / zone / machine type — and, for the
Caddy path, the hostname — if not given; the defaults below are fine for
10–100 users.

## 1. Project + APIs  (needs the gcloud CLI, `gcloud auth login`)

    gcloud projects create my-retalk --name="my-retalk"
    gcloud billing projects link my-retalk --billing-account=XXXXXX-XXXXXX-XXXXXX
    gcloud config set project my-retalk
    gcloud services enable compute.googleapis.com iap.googleapis.com

## 2. Lock down SSH (no public inbound ports)

    gcloud compute firewall-rules delete default-allow-ssh default-allow-rdp --quiet
    gcloud compute firewall-rules create allow-iap-ssh --direction=INGRESS --action=ALLOW \
      --rules=tcp:22 --source-ranges=35.235.240.0/20

## 3. Create the VM (no cloud identity — a stolen metadata token is then useless)

    gcloud compute instances create retalk-server --zone=us-central1-a \
      --machine-type=e2-micro --image-family=debian-12 --image-project=debian-cloud \
      --boot-disk-size=10GB --boot-disk-type=pd-standard --no-service-account --no-scopes

## 4. Install + run retalk

    gcloud compute ssh retalk-server --zone us-central1-a --tunnel-through-iap
    # on the VM:
    sudo apt-get update && sudo apt-get install -y python3-venv
    python3 -m venv ~/rt && ~/rt/bin/pip install retalk

## 5a. Expose with Caddy (own domain — default)

Pin the VM's IP and open HTTP/HTTPS for this VM only:

    IP=$(gcloud compute instances describe retalk-server --zone us-central1-a \
      --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    gcloud compute addresses create retalk-relay-ip --region=us-central1 --addresses="$IP"
    gcloud compute firewall-rules create retalk-relay-https --allow=tcp:80,tcp:443 \
      --source-ranges=0.0.0.0/0 --target-tags=retalk-relay
    gcloud compute instances add-tags retalk-server --zone=us-central1-a --tags=retalk-relay

Have the user create an A record for the hostname (e.g. `relay.example.com`)
pointing at `$IP` — **DNS only** if the zone is on Cloudflare, so Caddy can
answer the ACME challenge itself. Then on the VM:

    sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/gpg.key" | sudo gpg --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt" | sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt-get update && sudo apt-get install -y caddy
    printf "%s\n" "relay.example.com {" "    reverse_proxy 127.0.0.1:8766" "}" | sudo tee /etc/caddy/Caddyfile
    sudo systemctl enable --now caddy && sudo systemctl reload caddy

Caddy fetches and renews the certificate itself once DNS resolves.

## 5b. Or expose with a Cloudflare tunnel (no inbound ports, no domain needed)

See `cloudflare.md` (this folder). The tunnel's DNS route only works in the
Cloudflare account that owns the tunnel.

Either way, set `RETALK_SERVER_AUDIENCE` to the public https URL:

    RETALK_SERVER_DB=~/server.db RETALK_SERVER_HOST=127.0.0.1 RETALK_SERVER_PORT=8766 \
      RETALK_SERVER_AUDIENCE=https://relay.example.com ~/rt/bin/retalk-server

Give clients that audience as `RETALK_RELAY`. `--audience` (and the env var)
also accept a comma-separated list, so an old URL can stay valid while a
domain moves.

## Stop / delete

    gcloud compute instances stop retalk-server --zone us-central1-a     # stop: disk-only cost
    gcloud compute instances delete retalk-server --zone us-central1-a   # delete the VM
    gcloud compute firewall-rules delete allow-iap-ssh retalk-relay-https
    gcloud compute addresses delete retalk-relay-ip --region=us-central1  # if Caddy path was used
    gcloud projects delete my-retalk                                     # or remove everything
