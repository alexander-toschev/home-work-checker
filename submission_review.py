"""Non-executing similarity review. Findings never change grades automatically.

Keep reports_root private and separate for each course/semester. Templates and
identity overrides are instructor-controlled, never loaded from student files.
"""
import ast
import hashlib
import io
import json
import re
import tokenize
import unicodedata
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

_CYR = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                ['a','b','v','g','d','e','e','zh','z','i','y','k','l','m',
                 'n','o','p','r','s','t','u','f','kh','ts','ch','sh','shch',
                 '', 'y','', 'e','yu','ya']))


def identity_key(name, group):
    """Candidate key only: transliteration is not proof of identity."""
    def norm(s):
        s = unicodedata.normalize('NFKC', str(s or '')).casefold()
        return ''.join(_CYR.get(c, c) for c in s if c.isalnum())
    parts = re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', str(name or '')).casefold())
    return (tuple(sorted(norm(p) for p in parts)), norm(group))


def _normal(s):
    return ' '.join(unicodedata.normalize('NFKC', s).casefold().split())


def extract(path):
    """Read source only; notebook outputs/metadata never count as authorship."""
    raw = Path(path).read_bytes()
    text = raw.decode('utf-8-sig')
    if Path(path).suffix.lower() == '.ipynb':
        cells = json.loads(text)['cells']
        codes = [(i+1, ''.join(c.get('source', []))) for i,c in enumerate(cells) if c['cell_type']=='code']
        prose = [(i+1, ''.join(c.get('source', []))) for i,c in enumerate(cells) if c['cell_type']=='markdown']
    else:
        codes, prose = [(1, text)], []
    snippets, names, trees = [], [], []
    def snippet(s, cell, line, kind):
        s = _normal(s.strip('# \t\r\n'))
        if len(s) >= 40 and len(s.split()) >= 6:
            snippets.append({'text':s, 'cell':cell, 'line':line, 'kind':kind})
    for cell, code in codes:
        try:
            for t in tokenize.generate_tokens(io.StringIO(code).readline):
                if t.type == tokenize.COMMENT:
                    snippet(t.string, cell, t.start[0], 'comment')
        except (tokenize.TokenError, IndentationError):
            pass
        # Strip notebook magics before AST parsing, without executing them.
        python = '\n'.join('' if l.lstrip().startswith(('%','!')) else l for l in code.splitlines())
        try:
            tree = ast.parse(python)
        except SyntaxError:
            continue
        trees.append(ast.dump(tree, include_attributes=False))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                doc = ast.get_docstring(node)
                if doc:
                    snippet(doc, cell, getattr(node, 'lineno', 1), 'docstring')
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id.casefold() in
                       {'name','student_name','student','fio','full_name','student_fio'} for t in targets):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        names.append({'name':node.value.value,'cell':cell,'line':node.lineno})
    for cell, text in prose:
        for para in re.split(r'\n\s*\n', text):
            snippet(para, cell, 1, 'markdown')
        for m in re.finditer(r'(?im)^\s*(?:name|student|фио|имя)\s*[:=]\s*(.+)$', text):
            names.append({'name':m.group(1).strip(), 'cell':cell, 'line':text[:m.start()].count('\n')+1})
    return {'sha256':hashlib.sha256(raw).hexdigest(),'snippets':snippets,'names':names,'trees':trees}


def compare(records, templates=None):
    """Compare known same-assignment attempts. Code overlap alone is not a flag.

    record: path, name, group, assignment; optional student_id (trusted roster),
    expected_name / expected_group (trusted upload manifest), current.
    """
    templates = templates or {}
    baselines, prepared, findings, errors = {}, [], [], []
    for assignment, path in templates.items():
        try:
            baselines[str(assignment)] = extract(path)
        except Exception as e:
            errors.append({'template':str(path),'error':type(e).__name__})
    for record in records:
        r = dict(record)
        try:
            p = extract(r['path'])
        except Exception as e:
            errors.append({'path':str(r.get('path')),'error':type(e).__name__})
            continue
        base = baselines.get(str(r.get('assignment')))
        excluded = {s['text'] for s in base['snippets']} if base else set()
        r['profile'] = p
        r['snippets'] = {s['text']:s for s in p['snippets'] if s['text'] not in excluded}
        r['key'] = identity_key(r.get('name'), r.get('group'))
        r['template_available'] = base is not None
        prepared.append(r)
        if r.get('current', True):
            expected = r.get('expected_name')
            if expected and identity_key(expected, r.get('expected_group',r.get('group'))) != r['key']:
                findings.append({'status':'NEEDS_REVIEW','reason':'identity_mismatch',
                                 'files':[str(r['path'])], 'expected_name':expected,
                                 'claimed_name':r.get('name'), 'expected_group':r.get('expected_group'),
                                 'claimed_group':r.get('group')})
            expected_names = {n['name'] for n in base['names']} if base else set()
            for n in p['names']:
                if n['name'] in expected_names:
                    reason = 'template_name_retained'
                elif r.get('name') and identity_key(n['name'],r.get('group')) != r['key']:
                    reason = 'embedded_name_mismatch'
                else:
                    continue
                findings.append({'status':'NEEDS_REVIEW','reason':reason,'files':[str(r['path'])],
                                 'claimed_name':r.get('name'),'evidence':n})
    for a,b in combinations(prepared, 2):
        if not (a.get('current',True) or b.get('current',True)):
            continue
        assignment = a.get('assignment')
        if not assignment or assignment != b.get('assignment'):
            continue
        aid,bid = a.get('student_id'),b.get('student_id')
        if aid and bid and aid == bid:
            continue  # confirmed resubmission by the same student
        same_claim = a['key'] == b['key'] and bool(a['key'][0]) and bool(a['key'][1])
        if same_claim and not (aid and bid and aid != bid):
            # Unchanged name could be copying OR a legitimate resubmission.
            # Never silently resolve it using the submitted name alone.
            if a['profile']['sha256'] == b['profile']['sha256']:
                continue
            findings.append({'status':'IDENTITY_REVIEW','reason':'same_claimed_identity',
                             'files':[str(a['path']),str(b['path'])],
                             'note':'Confirm roster identity or alias before merging attempts.'})
            continue
        shared = sorted(set(a['snippets']) & set(b['snippets']))
        substantive = len(shared)>=2 or any(len(s)>=80 and len(s.split())>=10 for s in shared)
        if not substantive and not (same_claim and aid and bid and aid != bid):
            continue
        baseline = a['template_available'] and b['template_available']
        findings.append({'status':'NEEDS_REVIEW' if baseline else 'TEMPLATE_REQUIRED',
                         'reason':'same_claimed_identity_different_students' if same_claim else 'shared_explanations',
                         'assignment':assignment, 'files':[str(a['path']),str(b['path'])],
                         'students':[{'name':r.get('name'),'group':r.get('group'),'student_id':r.get('student_id')} for r in (a,b)],
                         'evidence':[{'text':s,'left':a['snippets'][s],'right':b['snippets'][s]} for s in shared[:10]],
                         'code_similarity_context_only':round(SequenceMatcher(None,'\n'.join(a['profile']['trees']),
                                                       '\n'.join(b['profile']['trees']),autojunk=False).ratio(),4),
                         'note':'Manual decision only. No automatic score change.'})
    return {'findings':findings,'read_errors':errors,'scanned':len(prepared),
            'limitations':['Heuristic signals are not proof of copying.',
                          'Missing templates require teacher comparison with the original task.',
                          'Names/transliterations require a trusted roster or confirmed alias.',
                          'Outputs are excluded. Short code similarity alone is never flagged.']}


def audit_history(reports_root, report_dir, grades, subs_dir, templates=None, identities=None):
    """Scan archived originals from this and earlier runs; never execute them."""
    root, current, subs = Path(reports_root).resolve(), Path(report_dir).resolve(), Path(subs_dir).resolve()
    identities = identities or {}  # keyed by archive path, instructor-controlled
    records = []
    for grade_file in sorted(root.glob('*/grades.json')):
        if grade_file.parent.resolve() == current:
            continue
        identity_file = grade_file.parent/'review_identities.json'
        historical_ids = json.loads(identity_file.read_text(encoding='utf-8')) if identity_file.exists() else {}
        for row in json.loads(grade_file.read_text(encoding='utf-8')).get('items',[]):
            p = (root/'submissions'/grade_file.parent.name/row['file']).resolve()
            if not p.is_relative_to(root/'submissions'):
                raise ValueError('Archive path outside submissions')
            records.append(dict(row,path=str(p),current=False,**identities.get(str(p),historical_ids.get(str(p),{}))))
    for row in grades:
        p = (subs/row['file']).resolve()
        if not p.is_relative_to(subs):
            raise ValueError('Archive path outside current snapshot')
        records.append(dict(row,path=str(p),current=True,**identities.get(str(p),{})))
    report = compare(records,templates)
    current.mkdir(parents=True,exist_ok=True)
    (current/'review_identities.json').write_text(json.dumps(identities,ensure_ascii=False,indent=2),encoding='utf-8')
    (current/'similarity_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Проверка сходства / Similarity review','',
           'Решение принимает преподаватель. Оценки автоматически не меняются. / Teacher decision only.','']
    for item in report['findings']:
        lines += [f"## {item['status']}: {item['reason']}", '', '```json',
                  json.dumps(item,ensure_ascii=False,indent=2),'```','']
    if not report['findings']:
        lines.append('Сигналы не найдены. Это не доказательство самостоятельности. / No signals found; not proof of independent work.')
    if report['read_errors']:
        lines += ['', 'Ошибки чтения / Read errors', '```json',json.dumps(report['read_errors'],ensure_ascii=False,indent=2),'```']
    (current/'similarity_review.md').write_text('\n'.join(lines),encoding='utf-8')
    return report
