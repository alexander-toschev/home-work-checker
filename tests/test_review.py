import json
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from submission_review import compare, identity_key, audit_history
from checker_handoff import calculate_penalty, build_handoff, CHECKER_VERSION

COMMENT = '# I chose this particular check because the last column may contain an empty value after filtering.'

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def record(self,name,source,student,**kw):
        p=self.root/name;p.write_text(source)
        return dict(path=str(p),name=student,group='11-601',assignment='NP-00',**kw)
    def test_transliteration_is_candidate_and_group_is_part_of_key(self):
        self.assertEqual(identity_key('Иван Иванов','11-601'),identity_key('Ivanov Ivan','11-601'))
        self.assertNotEqual(identity_key('Иван Иванов','11-601'),identity_key('Ivan Ivanov','11-602'))
    def test_identical_short_code_is_not_a_flag(self):
        a=self.record('a.py','x = sum(range(10))','A');b=self.record('b.py','x = sum(range(10))','B')
        self.assertEqual(compare([a,b])['findings'],[])
    def test_template_comments_excluded(self):
        a=self.record('a.py',COMMENT+'\nx=1','A');b=self.record('b.py',COMMENT+'\nx=2','B')
        template=self.root/'template.py';template.write_text(COMMENT+'\nx=None')
        self.assertEqual(compare([a,b],{'NP-00':template})['findings'],[])
    def test_shared_added_comment_has_locations_and_requires_teacher(self):
        a=self.record('a.py',COMMENT+'\nx=1','A');b=self.record('b.py',COMMENT+'\nx=2','B')
        template=self.root/'template.py';template.write_text('x=None')
        f=compare([a,b],{'NP-00':template})['findings'][0]
        self.assertEqual(f['status'],'NEEDS_REVIEW');self.assertEqual(f['evidence'][0]['left']['line'],1)
        self.assertEqual(compare([a,b])['findings'][0]['status'],'TEMPLATE_REQUIRED')
    def test_confirmed_resubmission_ignored(self):
        a=self.record('a.py',COMMENT+'\nx=1','Иван Иванов',student_id='s1')
        b=self.record('b.py',COMMENT+'\nx=2','Ivan Ivanov',student_id='s1')
        self.assertEqual(compare([a,b])['findings'],[])
    def test_unknown_same_identity_and_retained_name(self):
        a=self.record('a.py',COMMENT+'\nx=1','Иван Иванов')
        b=self.record('b.py',COMMENT+'\nx=2','Ivan Ivanov')
        self.assertEqual(compare([a,b])['findings'][0]['status'],'IDENTITY_REVIEW')
        c=self.record('c.py','student_name="Иван Иванов"','Петр Петров')
        self.assertEqual(compare([c])['findings'][0]['reason'],'embedded_name_mismatch')
    def test_outputs_ignored_and_cross_assignment_ignored(self):
        n={'cells':[{'cell_type':'code','source':['x=1'],'outputs':[{'text':[COMMENT]}]}]}
        a=self.record('a.ipynb',json.dumps(n),'A');b=self.record('b.ipynb',json.dumps(n),'B')
        self.assertEqual(compare([a,b])['findings'],[])
        a=self.record('a.py',COMMENT,'A');b=self.record('b.py',COMMENT,'B');b['assignment']='OTHER'
        self.assertEqual(compare([a,b])['findings'],[])
    def test_historical_archive_compared(self):
        root=self.root;old=root/'old';old.mkdir();subs=root/'submissions'/'old';subs.mkdir(parents=True)
        (subs/'a.py').write_text(COMMENT+'\nx=1')
        (old/'grades.json').write_text(json.dumps({'items':[{'file':'a.py','name':'A','group':'G','assignment':'NP-00'}]}))
        new=root/'new';new.mkdir();ns=root/'submissions'/'new';ns.mkdir();(ns/'b.py').write_text(COMMENT+'\nx=2')
        review=audit_history(root,new,[{'file':'b.py','name':'B','group':'G','assignment':'NP-00'}],ns)
        self.assertEqual(len(review['findings']),1);self.assertTrue((new/'similarity_review.json').exists())

class PenaltyTests(unittest.TestCase):
    def setUp(self):
        self.p={'score_kind':'raw','max_score':100,'penalty_mode':'linear',
                'start':'2026-09-01T00:00:00+03:00','due':'2026-09-11T00:00:00+03:00'}
    def test_boundary_timezone_half_and_cap(self):
        for at,expected in [('2026-09-10T21:00:00Z',80),('2026-09-16T00:00:00+03:00',40),('2026-10-01T00:00:00+03:00',0)]:
            self.assertEqual(calculate_penalty(80,self.p,at)['final_score'],expected)
    def test_invalid_scale_dates_or_already_penalized_hold(self):
        for raw,p,at in [(True,self.p,self.p['due']),(101,self.p,self.p['due']),
                         (80,dict(self.p,score_kind='final'),self.p['due']),
                         (80,self.p,'2026-09-11T00:00:00'),(80,{},self.p['due'])]:
            with self.assertRaises(ValueError):calculate_penalty(raw,p,at)
    def test_handoff_requires_receipt_and_does_not_write_google(self):
        with TemporaryDirectory() as d:
            r=Path(d);p=r/'a.py';p.write_text('x=1')
            grade={'file':'a.py','name':'A','group':'G','assignment':'NP-00','score':80,'status':'PASSED'}
            review={'findings':[],'read_errors':[]}
            report=build_handoff(r,r,[grade],review)
            self.assertFalse(report['writes_google']);self.assertEqual(report['attempts'][0]['status'],'NEEDS_REVIEW')
            self.assertEqual(report['checker_version'],CHECKER_VERSION)
            self.assertEqual(CHECKER_VERSION,(Path(__file__).resolve().parents[1]/'VERSION').read_text().strip())
            receipt={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'student_id':'s1','assignment':'NP-00','submitted_at':self.p['due']}
            report=build_handoff(r,r,[grade],review,{'NP-00':self.p},{'a.py':receipt})
            self.assertEqual(report['attempts'][0]['penalty']['final_score'],80)
            self.assertEqual(report['attempts'][0]['status'],'READY_FOR_ASSISTANT_COMPARISON')

if __name__=='__main__':unittest.main()
