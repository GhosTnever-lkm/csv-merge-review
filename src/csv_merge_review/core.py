"""Strict, deterministic three-way CSV merge logic."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class MergeError(ValueError):
    """Inputs cannot be merged unambiguously."""


@dataclass(frozen=True)
class CsvTable:
    columns: tuple[str, ...]
    rows: dict[str, dict[str, str]]
    order: tuple[str, ...]


@dataclass(frozen=True)
class MergeResult:
    columns: tuple[str, ...]
    key_column: str
    rows: tuple[dict[str, str], ...]
    conflicts: tuple[dict[str, str], ...]
    added: int
    removed: int
    auto_merged: int

    def report(self) -> dict[str, Any]:
        # Do not echo cell values in a report; CSV data may contain private records.
        return {
            "key_column": self.key_column,
            "summary": {"added": self.added, "removed": self.removed,
                        "auto_merged": self.auto_merged, "conflicts": len(self.conflicts)},
            "conflicts": list(self.conflicts),
            "merged_rows_written": len(self.rows),
        }


def read_csv(path: str | Path, key_column: str, max_bytes: int = 10 * 1024 * 1024) -> CsvTable:
    source=Path(path)
    try:
        if source.stat().st_size > max_bytes:
            raise MergeError(f"{source.name}: file exceeds the {max_bytes}-byte limit")
        with source.open("r",encoding="utf-8-sig",newline="") as f:
            reader=csv.DictReader(f); headers=reader.fieldnames
            if not headers: raise MergeError(f"{source.name}: CSV has no header row")
            if any(not h or not h.strip() for h in headers): raise MergeError(f"{source.name}: empty column name")
            if len(headers)!=len(set(headers)): raise MergeError(f"{source.name}: duplicate column names")
            if key_column not in headers: raise MergeError(f"{source.name}: key column {key_column!r} not found")
            rows={};order=[]
            for line,row in enumerate(reader,start=2):
                if None in row or any(v is None for v in row.values()):
                    raise MergeError(f"{source.name}: row {line} has a different number of fields than its header")
                key=row[key_column]
                if not key.strip(): raise MergeError(f"{source.name}: row {line} has an empty key")
                if key in rows: raise MergeError(f"{source.name}: duplicate key at row {line}")
                rows[key]=dict(row);order.append(key)
            return CsvTable(tuple(headers),rows,tuple(order))
    except MergeError: raise
    except (OSError,UnicodeError,csv.Error) as exc:
        raise MergeError(f"{source.name}: could not read valid UTF-8 CSV ({type(exc).__name__})") from None


def merge_tables(base: CsvTable, ours: CsvTable, theirs: CsvTable, key_column: str) -> MergeResult:
    expected=set(base.columns)
    for label,table in (("ours",ours),("theirs",theirs)):
        if set(table.columns)!=expected:
            raise MergeError(f"{label} CSV schema differs from base")
    if key_column not in expected: raise MergeError(f"key column {key_column!r} is missing")
    columns=base.columns
    key_order=list(base.order)
    key_order.extend(sorted((ours.rows.keys()|theirs.rows.keys())-base.rows.keys()))
    merged=[];conflicts=[];added=removed=auto=0
    absent=object()
    for key in key_order:
        b=base.rows.get(key,absent);o=ours.rows.get(key,absent);t=theirs.rows.get(key,absent)
        if b is absent:
            if o is absent: merged.append(dict(t));added+=1;continue
            if t is absent: merged.append(dict(o));added+=1;continue
            if o==t: merged.append(dict(o));added+=1;continue
            for field in columns:
                if o[field]!=t[field]: conflicts.append({"key":key,"field":field,"reason":"both_sides_added_different_values"})
            if not any(c["key"]==key for c in conflicts): merged.append(dict(o));added+=1
            continue
        if o is absent and t is absent: removed+=1;continue
        if o is absent:
            if t==b: removed+=1
            else: conflicts.append({"key":key,"field":"*","reason":"ours_deleted_theirs_edited"})
            continue
        if t is absent:
            if o==b: removed+=1
            else: conflicts.append({"key":key,"field":"*","reason":"theirs_deleted_ours_edited"})
            continue
        row={key_column:key};row_conflicts=[];did_merge=False
        for field in columns:
            if field==key_column:continue
            ov=o[field]!=b[field];tv=t[field]!=b[field]
            if ov and tv and o[field]!=t[field]:
                row_conflicts.append({"key":key,"field":field,"reason":"both_sides_changed_differently"})
            else:
                row[field]=o[field] if ov else t[field] if tv else b[field]
                did_merge |= ov and tv and o[field]==t[field]
        conflicts.extend(row_conflicts)
        if not row_conflicts:
            # Keep the baseline header order for stable output.
            merged.append({field:row[field] for field in columns})
            if did_merge: auto+=1
    return MergeResult(columns,key_column,tuple(merged),tuple(conflicts),added,removed,auto)


def render_csv(result: MergeResult) -> str:
    if result.conflicts:
        raise MergeError("refusing to write a merge containing conflicts")
    from io import StringIO
    out=StringIO(newline="")
    writer=csv.DictWriter(out,fieldnames=result.columns,lineterminator="\n",extrasaction="raise")
    writer.writeheader();writer.writerows(result.rows)
    return out.getvalue()


def render_json(result: MergeResult) -> str:
    return json.dumps(result.report(),ensure_ascii=False,indent=2,sort_keys=True)+"\n"
