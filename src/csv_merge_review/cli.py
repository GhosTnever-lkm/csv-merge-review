"""CLI for csv-merge-review."""
from __future__ import annotations
import argparse, os, sys, tempfile
from pathlib import Path
from . import __version__
from .core import MergeError,merge_tables,read_csv,render_csv,render_json

def atomic_write(path:Path,text:str)->None:
    path.parent.mkdir(parents=True,exist_ok=True);tmp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',newline='',dir=path.parent,prefix=f'.{path.name}.',delete=False) as f:
            tmp=f.name;f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp and os.path.exists(tmp):os.unlink(tmp)

def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(prog='csv-merge-review',description='Safely merge two CSV edits against a shared base using a unique key.')
    p.add_argument('base');p.add_argument('ours');p.add_argument('theirs');p.add_argument('--key',required=True,help='unique key column')
    p.add_argument('--output',type=Path,help='merged CSV destination; required when there are no conflicts')
    p.add_argument('--json-report',action='store_true',help='print a value-free conflict/summary report to stdout')
    p.add_argument('--max-bytes',type=int,default=10*1024*1024,help='size limit per input, default 10 MiB')
    p.add_argument('--version',action='version',version=f'%(prog)s {__version__}')
    a=p.parse_args(argv)
    if a.max_bytes<=0:p.error('--max-bytes must be a positive integer')
    paths=[Path(x).expanduser().resolve() for x in (a.base,a.ours,a.theirs)]
    output=a.output.expanduser().resolve() if a.output else None
    if output and output in paths:p.error('--output must not overwrite an input file')
    try:
        result=merge_tables(*(read_csv(x,a.key,a.max_bytes) for x in paths),a.key)
        if a.json_report:sys.stdout.write(render_json(result))
        if result.conflicts:
            if not a.json_report:
                for conflict in result.conflicts:
                    print(f"conflict: key={conflict['key']!r} field={conflict['field']!r} reason={conflict['reason']}",file=sys.stderr)
            return 1
        if output is None:
            if not a.json_report:p.error('--output is required when the merge has no conflicts')
        else:atomic_write(output,render_csv(result))
        if not a.json_report:print(f"Merged {len(result.rows)} rows; {result.added} added, {result.removed} removed, {result.auto_merged} equal concurrent edits.",file=sys.stderr)
        return 0
    except MergeError as e:
        print(f"csv-merge-review: {e}",file=sys.stderr);return 2
    except OSError as e:
        print(f"csv-merge-review: output failed ({type(e).__name__})",file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
