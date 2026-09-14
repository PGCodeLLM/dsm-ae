import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import vue from "@vitejs/plugin-vue";
import type { Plugin } from "vite";
import { defineConfig } from "vite";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)));
const repo = path.resolve(root, "..");
const blogMd = path.resolve(repo, "docs/blog_post.md");
const VIRTUAL = "virtual:blog.md";

function serveReports(): Plugin {
  const reports = path.resolve(repo, "reports");
  return {
    name: "serve-reports",
    configureServer(server) {
      server.middlewares.use("/reports", (req, res, next) => {
        const rel = decodeURIComponent((req.url || "/").split("?")[0]);
        const abs = path.resolve(reports, "." + rel);
        if (abs !== reports && !abs.startsWith(reports + path.sep)) {
          res.statusCode = 403;
          res.end("forbidden");
          return;
        }
        fs.stat(abs, (err, st) => {
          if (err) {
            next();
            return;
          }
          const file = st.isDirectory() ? path.join(abs, "index.html") : abs;
          fs.readFile(file, (e2, data) => {
            if (e2) {
              next();
              return;
            }
            const ext = path.extname(file);
            const types: Record<string, string> = {
              ".html": "text/html; charset=utf-8",
              ".json": "application/json; charset=utf-8",
              ".jsonl": "application/jsonl; charset=utf-8",
              ".css": "text/css; charset=utf-8",
              ".js": "text/javascript; charset=utf-8",
              ".md": "text/markdown; charset=utf-8",
            };
            res.setHeader("Content-Type", types[ext] || "application/octet-stream");
            res.end(data);
          });
        });
      });
    },
  };
}

function watchBlogMarkdown(): Plugin {
  return {
    name: "watch-blog-md",
    configureServer(server) {
      server.watcher.add(blogMd);
    },
    resolveId(id) {
      if (id === VIRTUAL) return "\0" + VIRTUAL;
    },
    load(id) {
      if (id === "\0" + VIRTUAL) {
        const text = fs.existsSync(blogMd) ? fs.readFileSync(blogMd, "utf8") : "";
        return `export default ${JSON.stringify(text)}`;
      }
    },
    handleHotUpdate({ file, server }) {
      if (path.resolve(file) !== blogMd) return;
      const mod = server.moduleGraph.getModuleById("\0" + VIRTUAL);
      if (mod) {
        server.moduleGraph.invalidateModule(mod);
        server.ws.send({ type: "full-reload" });
      }
    },
  };
}

export default defineConfig({
  root,
  plugins: [vue(), watchBlogMarkdown(), serveReports()],
  resolve: {
    alias: { "@": path.join(root, "src") },
  },
  server: {
    port: 5174,
    strictPort: true,
    fs: { allow: [repo] },
  },
});
