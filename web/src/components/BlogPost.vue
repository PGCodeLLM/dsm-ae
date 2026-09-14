<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue";
import mermaid from "mermaid";
import source from "virtual:blog.md";
import { renderMarkdown } from "../md";
import MetricResults from "./matrix/MetricResults.vue";
import SyndromeMatrix from "./matrix/SyndromeMatrix.vue";
import TrajectoryViewer from "./TrajectoryViewer.vue";

mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });

const root = ref<HTMLElement | null>(null);

function splitForEmbeds(md: string) {
  const parts: { html: string; embed?: "metrics" | "syndromes" | "traj" }[] = [];
  const chunks = md.split(/<!-- embed:(metrics|syndromes|traj) -->/);
  for (let i = 0; i < chunks.length; i++) {
    const piece = chunks[i];
    if (piece === "metrics" || piece === "syndromes" || piece === "traj") {
      parts.push({ html: "", embed: piece });
    } else if (piece.trim()) {
      parts.push({ html: renderMarkdown(piece) });
    }
  }
  return parts;
}

const sections = ref(splitForEmbeds(source));

async function draw() {
  await nextTick();
  if (!root.value) return;
  const nodes = root.value.querySelectorAll<HTMLElement>(".mermaid");
  if (!nodes.length) return;
  await mermaid.run({ nodes });
}

onMounted(draw);
watch(sections, draw, { flush: "post" });
</script>

<template>
  <article ref="root" class="blog">
    <p class="meta">
      Source <code>docs/blog_post.md</code> · Vite reloads when that file changes.
    </p>
    <template v-for="(sec, i) in sections" :key="i">
      <div v-if="sec.html" class="md" v-html="sec.html" />
      <div v-else-if="sec.embed === 'metrics'" class="embed-block">
        <MetricResults />
      </div>
      <div v-else-if="sec.embed === 'syndromes'" class="embed-block">
        <SyndromeMatrix />
      </div>
      <TrajectoryViewer v-else-if="sec.embed === 'traj'" featured-only />
    </template>
  </article>
</template>

<style scoped>
.blog :deep(h1) { font-size: 1.6rem; margin: 0 0 8px; }
.blog :deep(h2) { font-size: 1.2rem; margin: 28px 0 8px; }
.blog :deep(h3) { font-size: 1.05rem; margin: 20px 0 8px; }
.blog :deep(pre) {
  background: #f6f8fa; border: 1px solid #d0d7de; padding: 10px 12px;
  overflow-x: auto; border-radius: 4px;
}
.blog :deep(table) { border-collapse: collapse; font-size: 11px; }
.blog :deep(th), .blog :deep(td) { border: 1px solid #ccc; padding: 2px 4px; }
.blog :deep(.mermaid) { margin: 12px 0 16px; overflow-x: auto; }
.embed-block { margin: 16px 0 24px; overflow-x: auto; }
</style>
