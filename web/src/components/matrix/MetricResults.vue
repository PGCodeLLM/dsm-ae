<script setup lang="ts">
import { useMatrix } from "../../useMatrix";
const { data, error, visibleModels, cellFor } = useMatrix();
</script>

<template>
  <section class="block">
    <h2 id="metric-results">Metric results</h2>
    <div class="legend">
      <span>Pass rate</span>
      <span>0%</span>
      <i class="bar" />
      <span>100%</span>
    </div>
    <p v-if="error" class="meta">{{ error }}</p>
    <div v-else class="panel">
      <table>
        <thead>
          <tr>
            <th class="corner">Metric</th>
            <th v-for="m in visibleModels" :key="m">{{ m }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in data?.metrics || []" :key="row.id">
            <th class="row"><code>{{ row.id }}</code></th>
            <td
              v-for="m in visibleModels"
              :key="m"
              :style="cellFor(row.cells, m)?.color
                ? { background: cellFor(row.cells, m)!.color!, color: cellFor(row.cells, m)!.fg }
                : undefined"
              :class="{ 'not-run': cellFor(row.cells, m)?.status === 'NOT_RUN' }"
              :title="cellFor(row.cells, m)?.tip"
            >
              {{ cellFor(row.cells, m)?.label }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.block { margin: 0 0 20px; }
.legend { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #444; margin: 0 0 8px; }
.bar {
  width: 160px; height: 10px; border: 1px solid #999;
  background: linear-gradient(90deg, rgb(165,0,38), rgb(255,255,191), rgb(0,104,55));
}
.panel { overflow-x: auto; border: 1px solid #ccc; }
table { border-collapse: separate; border-spacing: 0; font-size: 12px; width: max-content; min-width: 100%; }
th, td { border: 1px solid #ccc; padding: 2px 5px; text-align: center; }
th.corner, th.row { text-align: left; position: sticky; left: 0; background: #fafafa; z-index: 1; }
thead th { background: #f5f5f5; position: sticky; top: 0; }
td.not-run { background: #eee; color: #555; font-style: italic; }
</style>
