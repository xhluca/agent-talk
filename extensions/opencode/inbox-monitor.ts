/**
 * agent-talk inbox monitor for opencode.
 *
 * This is the opencode equivalent of Claude Code's inbox monitor and of the pi
 * inbox extension (`extensions/inbox-monitor.ts`). A background follower
 * (`retalk receive --peer <fingerprint> --follow`) decrypts incoming messages
 * and appends each one as a JSON line to the user's spool file
 * `<user>/inbox.ndjson`. This plugin watches that spool and pushes each NEW
 * message into the running opencode session, so a peer's message surfaces on
 * its own and the agent takes a turn to handle it. No polling by the user, no
 * re-running the receive skill.
 *
 * opencode loads this as a plugin. A plugin is a JS/TS module that exports a
 * function receiving a context object and returning a hooks object. The context
 * gives us `client` (an SDK client already bound to this session's running
 * server) and `$` (a shell). We use the `event` hook to learn the active
 * session id, then inject each new spool line into that session with
 * `client.session.promptAsync(...)`, which durably admits an input and schedules
 * the agent loop. That is the opencode analog of pi's `sendMessage(..., {
 * triggerTurn: true })`.
 *
 * Which spool(s) to watch is set per session by the agent-talk init skill when
 * the delivery mode is "auto". It sets the environment variable
 * AGENT_TALK_OPENCODE_SPOOLS to a colon-separated list of absolute inbox.ndjson
 * paths before launching opencode. The plugin is inert (registers no watchers)
 * when that variable is unset, so installing it does not change any session that
 * has not opted in.
 *
 * Duplicate delivery is prevented two ways: a per-spool byte offset (only bytes
 * appended after the offset are read) and a set of already-delivered message
 * ids.
 */

import * as fs from "node:fs";
import type { Plugin } from "@opencode-ai/plugin";

// One spool line is a retalk NDJSON record: {"id","from","name","text"}.
// A shared contact arrives instead as {"id","from","name","kind":"contact",...}.
interface SpoolRecord {
	id?: string;
	from?: string;
	name?: string;
	text?: string;
	kind?: string;
}

interface Watched {
	path: string;
	offset: number; // bytes already consumed
	carry: string; // partial trailing line not yet terminated by "\n"
	watcher?: fs.FSWatcher;
	poll?: ReturnType<typeof setInterval>;
}

function spoolPaths(): string[] {
	const raw = process.env.AGENT_TALK_OPENCODE_SPOOLS ?? "";
	return raw
		.split(":")
		.map((s) => s.trim())
		.filter((s) => s.length > 0);
}

export const AgentTalkInboxMonitor: Plugin = async ({ client }) => {
	const watched = new Map<string, Watched>();
	const seenIds = new Set<string>();
	// The session to inject into. Learned from the first session event we see and
	// kept current as the user moves between sessions.
	let activeSession: string | undefined;
	// Records that arrive before any session is known are held here and flushed
	// once a session id is available.
	const pending: SpoolRecord[] = [];

	async function inject(rec: SpoolRecord) {
		if (!activeSession) {
			pending.push(rec);
			return;
		}
		const text = (rec.text ?? "").trim();
		if (!text) return;
		const who = rec.name || rec.from || "a peer";
		try {
			await client.session.promptAsync({
				path: { id: activeSession },
				body: {
					parts: [
						{
							type: "text",
							text: `New agent-talk message from ${who}:\n\n${text}`,
						},
					],
				},
			});
		} catch {
			// If the session went away, drop the active id so the next event
			// re-binds; keep the record for the next flush.
			activeSession = undefined;
			pending.push(rec);
		}
	}

	function deliver(rec: SpoolRecord) {
		// Skip contact records; those are handled by the import skill, not chat.
		if (rec.kind === "contact") return;
		if (!(rec.text ?? "").trim()) return;
		if (rec.id) {
			if (seenIds.has(rec.id)) return;
			seenIds.add(rec.id);
		}
		void inject(rec);
	}

	async function flushPending() {
		if (!activeSession || pending.length === 0) return;
		const batch = pending.splice(0, pending.length);
		for (const rec of batch) await inject(rec);
	}

	function drain(w: Watched) {
		let stat: fs.Stats;
		try {
			stat = fs.statSync(w.path);
		} catch {
			return; // file may not exist yet
		}
		if (stat.size < w.offset) {
			// File was truncated or rotated; start over from the beginning.
			w.offset = 0;
			w.carry = "";
		}
		if (stat.size === w.offset) return;
		let chunk = "";
		try {
			const fd = fs.openSync(w.path, "r");
			try {
				const len = stat.size - w.offset;
				const buf = Buffer.alloc(len);
				const read = fs.readSync(fd, buf, 0, len, w.offset);
				chunk = buf.subarray(0, read).toString("utf-8");
				w.offset += read;
			} finally {
				fs.closeSync(fd);
			}
		} catch {
			return;
		}
		const data = w.carry + chunk;
		const parts = data.split("\n");
		w.carry = parts.pop() ?? ""; // last element is an unterminated remainder
		for (const line of parts) {
			const trimmed = line.trim();
			if (!trimmed) continue;
			let rec: SpoolRecord;
			try {
				rec = JSON.parse(trimmed) as SpoolRecord;
			} catch {
				continue; // ignore non-JSON / partial lines
			}
			deliver(rec);
		}
	}

	function startWatch(path: string) {
		if (watched.has(path)) return;
		const w: Watched = { path, offset: 0, carry: "" };
		// Seek to end so we only surface messages that arrive from now on; the
		// backlog is available through the receive/history skills.
		try {
			w.offset = fs.statSync(path).size;
		} catch {
			w.offset = 0; // file not created yet; drain() handles creation
		}
		try {
			w.watcher = fs.watch(path, () => drain(w));
		} catch {
			// File may not exist yet; the poll below covers creation and also
			// backs up fs.watch, which can miss events on some filesystems.
		}
		w.poll = setInterval(() => drain(w), 1000);
		watched.set(path, w);
	}

	// Start watchers immediately at plugin load; the plugin function runs once
	// per session, so this is the opencode analog of pi's session_start.
	for (const p of spoolPaths()) startWatch(p);

	return {
		async event({ event }) {
			// Latch onto the active session id from any session-scoped event, then
			// flush anything that arrived before we knew the session.
			const props = (event as { properties?: Record<string, unknown> })
				.properties;
			const id =
				(props?.sessionID as string | undefined) ??
				((props?.info as { id?: string } | undefined)?.id ?? undefined);
			if (id && id !== activeSession) {
				activeSession = id;
				await flushPending();
			}
		},
	};
};

export default AgentTalkInboxMonitor;
