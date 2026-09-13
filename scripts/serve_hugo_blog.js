#!/usr/bin/env node
/**
 * Serve the built Hugo blog (reports/blog/hugo) on a local port.
 *
 *   node scripts/serve_hugo_blog.js
 *   node scripts/serve_hugo_blog.js --port 8766
 *   PORT=8766 node scripts/serve_hugo_blog.js
 *
 * Does not replace dsm-ae serve-queue (8765). This is only the Hugo tree.
 */
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const DEFAULT_ROOT = path.join(ROOT, "reports", "blog", "hugo");
const DEFAULT_PORT = 8766;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".jsonl": "application/jsonl; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
};

function parseArgs(argv) {
  let port = Number(process.env.PORT) || DEFAULT_PORT;
  let root = DEFAULT_ROOT;
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--port" && argv[i + 1]) {
      port = Number(argv[++i]);
    } else if (a.startsWith("--port=")) {
      port = Number(a.slice("--port=".length));
    } else if (a === "--root" && argv[i + 1]) {
      root = path.resolve(argv[++i]);
    } else if (a === "-h" || a === "--help") {
      console.log("usage: node scripts/serve_hugo_blog.js [--port 8766] [--root DIR]");
      process.exit(0);
    }
  }
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    console.error("invalid port");
    process.exit(1);
  }
  return { port, root };
}

function safeJoin(root, urlPath) {
  const decoded = decodeURIComponent((urlPath || "/").split("?")[0]);
  const cleaned = path.posix.normalize("/" + decoded).replace(/^\/+/, "");
  const abs = path.resolve(root, cleaned);
  const rootAbs = path.resolve(root);
  if (abs !== rootAbs && !abs.startsWith(rootAbs + path.sep)) {
    return null;
  }
  return abs;
}

function send(res, status, body, headers) {
  res.writeHead(status, headers || {});
  res.end(body);
}

function serveFile(res, filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const type = MIME[ext] || "application/octet-stream";
  fs.readFile(filePath, (err, data) => {
    if (err) {
      send(res, 500, "read error\n", { "Content-Type": "text/plain" });
      return;
    }
    send(res, 200, data, { "Content-Type": type, "Cache-Control": "no-cache" });
  });
}

function main() {
  const { port, root } = parseArgs(process.argv);
  if (!fs.existsSync(path.join(root, "index.html"))) {
    console.error("no index.html under", root);
    console.error("build first: python3 scripts/generate_blog_ui.py");
    process.exit(1);
  }

  const server = http.createServer((req, res) => {
    const dest = safeJoin(root, req.url || "/");
    if (!dest) {
      send(res, 403, "forbidden\n", { "Content-Type": "text/plain" });
      return;
    }
    fs.stat(dest, (err, st) => {
      if (!err && st.isDirectory()) {
        const index = path.join(dest, "index.html");
        fs.stat(index, (e2) => {
          if (e2) {
            send(res, 404, "not found\n", { "Content-Type": "text/plain" });
            return;
          }
          serveFile(res, index);
        });
        return;
      }
      if (err || !st.isFile()) {
        send(res, 404, "not found\n", { "Content-Type": "text/plain" });
        return;
      }
      serveFile(res, dest);
    });
  });

  server.listen(port, "127.0.0.1", () => {
    console.log(`Hugo blog  http://127.0.0.1:${port}/`);
    console.log(`root       ${root}`);
  });
}

main();
