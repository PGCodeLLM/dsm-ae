# DSM-AE Vue blog

Vite + Vue 3. Serves `docs/blog_post.md` and reloads when that file changes.

```bash
cd web
npm install
python3 web/scripts/extract_matrix_data.py   # refresh reports/matrix/vue-data.json
npm run dev
```

Open http://127.0.0.1:5174/

- **Blog** — markdown, mermaid pipelines, trajectory viewer at §1.5 / Appendix A
- **Matrix** — Vue sections: syndrome matrix, decision trees, metric results
- **Trajectories** — `TrajectoryViewer` over `reports/blog/trajectories/`

Refresh matrix JSON after regenerating `reports/dsm-ae-matrix.html`.
