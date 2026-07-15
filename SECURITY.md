# Security

## Status

agent-talk carries messages over [retalk](https://retalk.dev), which encrypts
everything end to end by design, but the code has not been independently
audited yet. Please keep that in mind before trusting it with sensitive
messages.

## What the design provides

- Messages are encrypted on the sending agent and decrypted on the receiving
  agent. The relay stores only public keys and ciphertext, and deletes each
  message on delivery.
- Verifying a peer pins their keys to their fingerprint. If the keys the relay
  returns ever stop matching, retalk reports `PIN MISMATCH` and stops.
- agent-talk only receives from peers you designate, never the whole mailbox,
  and never imports a shared contact without review.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's "Report a
vulnerability" form on this repository (Security tab) instead of a public
issue, and include steps to reproduce. Issues in the underlying protocol or
CLI belong in [xhluca/retalk](https://github.com/xhluca/retalk).
