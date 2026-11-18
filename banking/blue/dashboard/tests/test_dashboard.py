import copy
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from domain import DataError, groups, sample, validate
class ContractTests(unittest.TestCase):
    def test_pending_is_not_confirmed(self):
        left,right,_,_=groups(sample('평가 대기'))
        self.assertEqual(len(left),1)
        self.assertEqual(len(right),2)
        self.assertEqual(sum(f['validation']=='confirmed_attack' for f in right),0)
    def test_unknown_baseline_is_not_extra_detection(self):
        d=sample();d['findings'][1]['baseline_detected']=None
        _,right,unassigned,_=groups(validate(d))
        self.assertEqual(len(right),1)
        self.assertEqual(len(unassigned),1)
    def test_false_positive_is_separate(self):
        d=sample();d['findings'][1]['validation']='false_positive'
        _,right,_,rejected=groups(validate(d))
        self.assertEqual(len(right),1)
        self.assertEqual(len(rejected),1)
    def test_fabricated_evidence_rejected(self):
        d=sample();d['findings'][0]['evidence_log_ids']=['nonexistent']
        with self.assertRaises(DataError):validate(d)
    def test_all_states_render(self):
        a=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
        self.assertEqual(len(a.exception),0)
        for mode in ['평가 대기','정상 업무','분석 실패','추가 탐지 확인']:
            a.sidebar.selectbox[0].set_value(mode).run()
            self.assertEqual(len(a.exception),0,mode)
    def test_missing_real_data_does_not_show_demo(self):
        a=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
        a.radio[0].set_value('실제 결과 파일').run()
        self.assertEqual(len(a.exception),0)
        self.assertEqual(len(a.tabs),0)
    def test_recommendation_selection(self):
        a=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
        a.selectbox('action_finding').set_value('F-002').run()
        self.assertEqual(len(a.exception),0)
        self.assertTrue(any('업무 승인 내역' in str(x.value) for x in a if x.type=='html'))
    def test_real_file_and_corrupt_file(self):
        import os, tempfile, json
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            run=Path(td)/'run1';run.mkdir()
            target=run/'evaluation.json'
            target.write_text(json.dumps(sample(),ensure_ascii=False),encoding='utf-8')
            with patch.dict(os.environ,{'DASHBOARD_DATA_DIR':td}):
                a=AppTest.from_file(str(ROOT/'app.py'),default_timeout=15).run()
                a.radio[0].set_value('실제 결과 파일').run()
                self.assertEqual(len(a.exception),0)
                self.assertEqual(len(a.tabs),3)
                target.write_text('{broken',encoding='utf-8')
                a.run()
                self.assertEqual(len(a.exception),0)
                self.assertTrue(len(a.error)>0)
                self.assertEqual(len(a.tabs),0)
if __name__=='__main__':unittest.main()
