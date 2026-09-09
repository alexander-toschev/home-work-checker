"""Core harness regressions; no Google Sheets export or real student data."""
import ast
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

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
    def test_valid_payload(self):
        p=self.h['parse_last_payload']('{"name":"A","group":"G","assignment":"NP-00","score":100}')
        self.assertEqual(p['score'],100)
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
