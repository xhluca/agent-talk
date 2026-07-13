/**
 * agent-talk inbox monitor for pi.
 *
 * This is the pi equivalent of Claude Code's inbox monitor. A background
 * follower (`retalk receive --peer <fingerprint> --follow`) decrypts incoming
 * messages and appends each one as a JSON line to the user's spool file
 * `<user>/inbox.ndjson`. This extension watches that spool and pushes each NEW
 * message into the active pi session with `pi.sendMessage(..., { triggerTurn:
 * true })`, so a peer's message surfaces on its own and the agent takes a turn
 * to handle it. No polling by the user, no re-running the receive skill.
 *
 * Which spool(s) to watch is set per session by the agent-talk init skill when
 * the delivery mode is "auto". It sets the environment variable
 * AGENT_TALK_PI_SPOOLS to a colon-separated list of absolute inbox.ndjson
 * paths before launching pi. The extension is inert (registers no watchers)
 * when that variable is unset, so installing it does not change any session
 * that has not opted in.
 *
 * Duplicate delivery is prevented two ways: a per-spool byte offset (only bytes
 * appended after the offset are read) and a set of already-delivered message
 * ids.
 */

import * as fs from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

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
	const raw = process.env.AGENT_TALK_PI_SPOOLS ?? "";
	return raw
		.split(":")
		.map((s) => s.trim())
		.filter((s) => s.length > 0);
}

export default function (pi: ExtensionAPI) {
	// Defer all resource startup to session_start (extension factories may run
	// in invocations that never start a session).
	const watched = new Map<string, Watched>();
	const seenIds = new Set<string>();

	function deliver(rec: SpoolRecord) {
		// Skip contact records; those are handled by the import skill, not chat.
		if (rec.kind === "contact") return;
		const text = (rec.text ?? "").trim();
		if (!text) return;
		if (rec.id) {
			if (seenIds.has(rec.id)) return;
			seenIds.add(rec.id);
		}
		const who = rec.name || rec.from || "a peer";
		pi.sendMessage(
			{
				customType: "agent-talk-inbox",
				content: `New agent-talk message from ${who}:\n\n${text}`,
				display: true,
				details: { from: rec.from, name: rec.name, id: rec.id },
			},
			// Idle: trigger a turn now. Streaming: queued and delivered after the
			// current assistant turn finishes its tool calls (steer default).
			{ triggerTurn: true },
		);
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

	function stopAll() {
		for (const w of watched.values()) {
			try {
				w.watcher?.close();
			} catch {
				/* ignore */
			}
			if (w.poll) clearInterval(w.poll);
		}
		watched.clear();
	}

	pi.on("session_start", async (_event, ctx) => {
		const paths = spoolPaths();
		for (const p of paths) startWatch(p);
		if (paths.length > 0 && ctx.hasUI) {
			ctx.ui.notify(
				`agent-talk: watching ${paths.length} inbox spool(s) for incoming messages`,
				"info",
			);
		}
	});

	pi.on("session_shutdown", async () => {
		stopAll();
	});
}
