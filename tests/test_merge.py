from __future__ import annotations
import os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from csv_merge_review.core import MergeError, merge_tables, read_csv, render_csv, render_json

class MergeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.d=Path(self.tmp.name)
  self.base=self.d/'base.csv';self.ours=self.d/'ours.csv';self.theirs=self.d/'theirs.csv'
 def tearDown(self):self.tmp.cleanup()
 def pair(self,b,o,t):
  for p,s in zip((self.base,self.ours,self.theirs),(b,o,t)):p.write_text(s,encoding='utf-8')
 def merge(self):return merge_tables(read_csv(self.base,'id'),read_csv(self.ours,'id'),read_csv(self.theirs,'id'),'id')
 def test_merges_disjoint_field_edits(self):
  self.pair('id,name,price\n1,apple,1\n','id,name,price\n1,green apple,1\n','id,name,price\n1,apple,2\n')
  result=self.merge();self.assertFalse(result.conflicts);self.assertEqual(result.rows[0],{'id':'1','name':'green apple','price':'2'})
 def test_reports_conflict_when_both_change_same_field_differently(self):
  self.pair('id,name\n1,old\n','id,name\n1,ours\n','id,name\n1,theirs\n')
  result=self.merge();self.assertEqual(result.conflicts[0]['reason'],'both_sides_changed_differently')
 def test_identical_concurrent_edits_merge_without_conflict(self):
  self.pair('id,name\n1,old\n','id,name\n1,new\n','id,name\n1,new\n')
  result=self.merge();self.assertFalse(result.conflicts);self.assertEqual(result.auto_merged,1)
 def test_one_sided_edit_wins(self):
  self.pair('id,name\n1,old\n','id,name\n1,new\n','id,name\n1,old\n')
  self.assertEqual(self.merge().rows[0]['name'],'new')
 def test_add_on_one_side_is_preserved(self):
  self.pair('id,name\n','id,name\n1,one\n','id,name\n')
  result=self.merge();self.assertEqual(result.added,1);self.assertEqual(result.rows[0]['id'],'1')
 def test_identical_additions_merge(self):
  self.pair('id,name\n','id,name\n1,one\n','id,name\n1,one\n')
  self.assertEqual(len(self.merge().rows),1)
 def test_divergent_additions_conflict_by_field(self):
  self.pair('id,name\n','id,name\n1,one\n','id,name\n1,two\n')
  self.assertEqual(self.merge().conflicts[0]['reason'],'both_sides_added_different_values')
 def test_delete_against_unchanged_row_deletes(self):
  self.pair('id,name\n1,one\n','id,name\n','id,name\n1,one\n')
  result=self.merge();self.assertEqual(result.removed,1);self.assertEqual(result.rows,())
 def test_delete_against_edit_conflicts(self):
  self.pair('id,name\n1,one\n','id,name\n','id,name\n1,two\n')
  self.assertEqual(self.merge().conflicts[0]['reason'],'ours_deleted_theirs_edited')
 def test_schema_mismatch_is_rejected(self):
  self.pair('id,name\n1,x\n','id,title\n1,x\n','id,name\n1,x\n')
  with self.assertRaisesRegex(MergeError,'schema differs'):self.merge()
 def test_duplicate_keys_are_rejected(self):
  self.pair('id,name\n1,x\n1,y\n','id,name\n','id,name\n')
  with self.assertRaisesRegex(MergeError,'duplicate key'):self.merge()
 def test_csv_writer_quotes_commas_newlines(self):
  self.pair('id,note\n1,old\n','id,note\n1,"hello, world"\n','id,note\n1,old\n')
  self.assertIn('"hello, world"',render_csv(self.merge()))
 def test_conflict_report_never_includes_cell_values(self):
  self.pair('id,name\nprivate-id,secret-base\n','id,name\nprivate-id,secret-ours\n','id,name\nprivate-id,secret-theirs\n')
  report=render_json(self.merge());self.assertIn('private-id',report);self.assertNotIn('secret-',report)
 def test_cli_never_writes_partial_merge_on_conflict(self):
  self.pair('id,name\n1,base\n','id,name\n1,left\n','id,name\n1,right\n')
  out=self.d/'merged.csv'
  proc=subprocess.run([sys.executable,'-m','csv_merge_review.cli',str(self.base),str(self.ours),str(self.theirs),'--key','id','--output',str(out)],cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True)
  self.assertEqual(proc.returncode,1);self.assertFalse(out.exists());self.assertIn('both_sides_changed_differently',proc.stderr)

if __name__=='__main__':unittest.main()
