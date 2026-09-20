"""Core harness regressions; no Google Sheets export or real student data."""
import ast
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'home-work-checker.ipynb'
def load_harness():
    source = ''.join(json.loads(SOURCE.read_text())['cells'][0]['source'])
    compile(source, str(SOURCE), 'exec')
    # Do not run the configured inbox/UI. Keep the actual runner implementation.
    source = source.split('# ==== UI')[0]
    namespace = {}
    exec(compile(source, str(SOURCE), 'exec'), namespace)
    namespace['VERBOSITY'] = 0
    return namespace

class CheckerTests(unittest.TestCase):
    def setUp(self): self.h = load_harness()
    def test_original_is_archived_before_execution(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=root/'inbox';target.mkdir()
            source='from pathlib import Path\nPath(__file__).write_text("changed")\nprint(\'{"name":"A","group":"G","assignment":"NP-00","score":85}\')'
            (target/'a.py').write_text(source)
            with contextlib.redirect_stdout(io.StringIO()):
                result=self.h['run_checks'](target,['*.py'],20,False,root/'reports',True,0)
            run=Path(result['report_dir']).name
            self.assertEqual((root/'reports'/'submissions'/run/'a.py').read_text(),source)
            self.assertFalse(result['assistant_handoff']['writes_google'])
            self.assertEqual(result['assistant_handoff']['attempts'][0]['status'],'NEEDS_REVIEW')
    def test_valid_payload(self):
        p=self.h['parse_last_payload']('{"name":"A","group":"G","assignment":"NP-00","score":100}')
        self.assertEqual(p['score'],100)
    def test_stderr_warning_after_grade_does_not_hide_payload(self):
        import nbformat
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'warning.ipynb'
            cell = nbformat.v4.new_code_cell('pass')
            cell.outputs = [
                nbformat.v4.new_output('stream', name='stdout', text='{"name":"A","group":"G","assignment":"NP-00","score":100}\n'),
                nbformat.v4.new_output('stream', name='stderr', text='RuntimeWarning: Mean of empty slice.\n'),
            ]
            nbformat.write(nbformat.v4.new_notebook(cells=[cell]), path)
            class Client:
                def __init__(self, *args, **kwargs): pass
                def execute(self): pass
            with patch.dict(self.h, {'NotebookClient': Client, 'NBCLIENT_AVAILABLE': True}):
                result = self.h['run_notebook'](path, 20)
            self.assertEqual(result['payload']['score'], 100)
            self.assertEqual(result['payload']['name'], 'A')
    def test_nonfinite_and_boolean_scores_rejected(self):
        for score in ['NaN','Infinity','true','"nan"']:
            self.assertIsNone(self.h['parse_last_payload']('{"score":'+score+'}')['score'])
    def test_batch_continues_after_crash_or_missing_json(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); target=root/'inbox';target.mkdir()
            (target/'a_crash.py').write_text('raise ValueError("test")')
            (target/'b_missing.py').write_text('print("no grade")')
            (target/'c_ok.py').write_text('print(\'{"name":"A","group":"G","assignment":"NP-00","score":85}\')')
            with contextlib.redirect_stdout(io.StringIO()):
                result=self.h['run_checks'](target,['*.py'],20,False,root/'reports',True,0)
            self.assertEqual([r['status'] for r in result['grades_rows']],['FAILED','FAILED','PASSED'])
            self.assertEqual([r['score'] for r in result['grades_rows']],[None,None,85])
            self.assertTrue((Path(result['report_dir'])/'grades.csv').exists())

if __name__ == '__main__': unittest.main()
