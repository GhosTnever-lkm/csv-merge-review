# Changelog

## 0.1.2 - 2026-10-13

- Keep package and CLI version in sync with the release.
- Reject malformed quoted CSV records instead of accepting a partial parse.
- Report `mergeable_rows: null` when conflicts prevent writing an output file.
- Publish installable wheel and source distribution with SHA-256 checksums; align CI smoke coverage for Windows.

## 0.1.1 - 2026-10-11

- CI now also runs the test suite on Windows (windows-latest), not only Ubuntu.


## 0.1.0 - 2026-10-11

- Initial release: conservative three-way CSV merge by a unique key.
- Combine disjoint changes, accept identical concurrent edits, and report divergent edits or delete/edit conflicts.
- Never write a partial merged CSV when conflicts exist; value-free JSON conflict report is available.
