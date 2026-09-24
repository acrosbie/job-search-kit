#!/usr/bin/env node
// Platform check, phase 0. Throwaway.
// A local connector (MCP server over stdio) with one tool, fetch_board, which fetches a public
// Greenhouse board from this computer. It exists to answer two questions: can a plugin's local
// connector fetch job boards when Cowork's sandbox can't, and which Node runs it (Claude's
// built-in runtime or one the user installed). No npm packages: newline-delimited JSON-RPC by hand.

const https = require("https");
const os = require("os");
const readline = require("readline");

const UA = "Mozilla/5.0 (compatible; job-search-kit-platform-check/0.1)";

function redact(s) {
  const home = os.homedir();
  return home && home.length > 3 ? s.split(home).join("~") : s;
}

function getJson(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { "User-Agent": UA, Accept: "application/json" }, timeout: 20000 }, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (c) => (body += c));
      res.on("end", () => {
        if (res.statusCode !== 200) return reject(new Error(`HTTP ${res.statusCode}`));
        try { resolve(JSON.parse(body)); } catch (e) { reject(e); }
      });
    });
    req.on("timeout", () => req.destroy(new Error("timed out")));
    req.on("error", reject);
  });
}

async function fetchBoard(token) {
  const t = Date.now();
  const runtime = {
    "runs on": "this computer, started by the Claude app",
    node: process.version,
    "node program": redact(process.execPath),
    platform: `${process.platform} ${os.release()} (${process.arch})`,
  };
  try {
    const data = await getJson(`https://boards-api.greenhouse.io/v1/boards/${encodeURIComponent(token)}/jobs`);
    const jobs = data.jobs || [];
    return { board: token, ok: true, jobs: jobs.length, "first titles": jobs.slice(0, 3).map((j) => j.title),
             seconds: (Date.now() - t) / 1000, ...runtime };
  } catch (e) {
    return { board: token, ok: false, error: String(e.message || e), seconds: (Date.now() - t) / 1000, ...runtime };
  }
}

const TOOLS = [{
  name: "fetch_board",
  description: "Platform check (test): fetch a public Greenhouse job board from this computer and report how many jobs it lists and which Node runtime ran the fetch.",
  inputSchema: {
    type: "object",
    properties: { token: { type: "string", description: "Greenhouse board token, for example greenhouse" } },
    additionalProperties: false,
  },
}];

function send(msg) { process.stdout.write(JSON.stringify(msg) + "\n"); }

async function handle(msg) {
  const { id, method, params } = msg;
  if (id === undefined) return; // notifications, e.g. notifications/initialized
  if (method === "initialize") {
    return send({ jsonrpc: "2.0", id, result: {
      protocolVersion: (params && params.protocolVersion) || "2025-06-18",
      capabilities: { tools: {} },
      serverInfo: { name: "platform-check-local", version: "0.0.1" },
    } });
  }
  if (method === "ping") return send({ jsonrpc: "2.0", id, result: {} });
  if (method === "tools/list") return send({ jsonrpc: "2.0", id, result: { tools: TOOLS } });
  if (method === "tools/call") {
    const name = params && params.name;
    if (name !== "fetch_board") {
      return send({ jsonrpc: "2.0", id, error: { code: -32602, message: `unknown tool ${name}` } });
    }
    const token = (params.arguments && params.arguments.token) || "greenhouse";
    const result = await fetchBoard(token);
    return send({ jsonrpc: "2.0", id, result: {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      isError: !result.ok,
    } });
  }
  send({ jsonrpc: "2.0", id, error: { code: -32601, message: `method not found: ${method}` } });
}

readline.createInterface({ input: process.stdin }).on("line", (line) => {
  if (!line.trim()) return;
  let msg;
  try { msg = JSON.parse(line); } catch (e) {
    return send({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } });
  }
  handle(msg).catch((e) => send({ jsonrpc: "2.0", id: msg.id, error: { code: -32603, message: String(e) } }));
});
