# Changelog

## 0.1.0 - 2026-10-11

- Initial release: conservative three-way CSV merge by a unique key.
- Combine disjoint changes, accept identical concurrent edits, and report divergent edits or delete/edit conflicts.
- Never write a partial merged CSV when conflicts exist; value-free JSON conflict report is available.
