"""Closed diagnostic projections never echo input text or infer a UI effect."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safe_span_progress import project,validate_safe_event
class SafeProgressTests(unittest.TestCase):
 def test_exception_and_phase_projection_drop_secret_payloads(self):
  secret='synthetic-secret-token';row={'event':'error','label':'WebDriver.call','category':'normal-go-touch-request','message':secret,'arguments':{'password':secret},'exception':{'class':'NativeUIError','closedCodes':['PHONE_BOUND_STATE',secret],'message':secret,'sourceFrames':[{'sourceFile':'private/'+secret,'function':'invoke','line':42}]}}
  value=project(row,{'tests/device/run.py'},{'PHONE_BOUND_STATE'});raw=json.dumps(value);self.assertNotIn(secret,raw);self.assertIn('PHONE_BOUND_STATE',raw);self.assertEqual('<runtime>',value['exception']['frames'][0]['file'])
  value.update(schemaVersion=1,sequence=1,epochMs=1,phase='adapter');self.assertTrue(validate_safe_event(value,{'domain-enter'},{'tests/device/run.py'},{'PHONE_BOUND_STATE'}))
 def test_missing_or_error_observation_is_unknown_never_false_or_pressed(self):
  for value in({'event':'normal-ui-read','control':'Go','outcome':'error'},{'event':'normal-phone-ime-read','outcome':'invalid'}):
   row=project(value,set(),set());self.assertNotIn(False,row.values());self.assertNotIn('pressed',json.dumps(row))
  self.assertIsNone(project({'event':'normal-ui-read','control':'foreign-secret','outcome':'actual','present':True},set(),set()))
  self.assertFalse(validate_safe_event({'schemaVersion':1,'sequence':1,'phase':'adapter','event':'observation','rawSecret':'leak'},set(),set(),set()))
if __name__=='__main__':unittest.main()
