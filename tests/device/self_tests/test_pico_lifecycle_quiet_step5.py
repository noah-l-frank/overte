"""Actual Background5 quiet lifetimes and sealed callbacks with declared Qt/SDK.

These component counters do not qualify the complete born-host flow.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys,unittest,json,tempfile,os,subprocess,hashlib
from unittest.mock import patch
from adapters.pico4.lifecycle_drive import AvatarDisplacement
from adapters.pico4 import lifecycle_background_state5 as state5
from adapters.pico4 import lifecycle_background_owner as owner
from adapters.pico4 import lifecycle_source_raw as raw4
from adapters.pico4 import lifecycle_quiet_step5 as quiet
from self_tests import test_pico_lifecycle_background_state5 as fixture_module
from adapters.normal_ui import NativeUIError
class LifecycleQuietStep5Tests(unittest.TestCase):
 def fixture(self):
  f=fixture_module.LifecycleBackgroundState5Tests();f.setUp();self.addCleanup(f.doCleanups);f.prepare();return f
 def prefix(self):
  f=self.fixture();h=f.owner.state5;observed=[];previous=sys.getprofile();code=state5.LifecycleBackgroundState5.quiet_step.__code__
  def profile(frame,event,value):
   if event=='return' and frame.f_code is code and type(value) is tuple:
    observed.append(value[1]);raise NativeUIError('Intentional private first quiet return boundary')
  try:
   sys.setprofile(profile)
   with self.assertRaises(NativeUIError):f.owner.run_owned()
  finally:sys.setprofile(previous)
  self.assertEqual(1,len(observed));self.assertIsNone(h.quiet.active);return f,observed[0]
 def counts(self,f):return f.bank.archive.state['reads'],len(f.seams.history.commands)
 def test_public_packet_default_escape_still_available(self):
  f=self.fixture()
  with f.seams.lock.held():
   row=f.owner.capture();packet=f.owner.packet(row)
   self.assertEqual(f.owner.pid,packet['drive']['processId']);self.assertTrue(f.owner.state5.results)
 def test_actual_normal_prefix_creates_sealed_non_escaping_window(self):
  f,handle=self.prefix();h=f.owner.state5
  self.assertEqual(3*handle.seal[5]+6*65536,handle.stage.reserve)
  self.assertIsNotNone(handle.window.previous);self.assertIsNone(handle.stage.result)
 def test_book_instance_shadow_refused_without_foreign_callback(self):
  f,handle=self.prefix();h=f.owner.state5;calls=[]
  def foreign(*args):calls.append(True);return None
  h.quiet.observe=foreign;before=self.counts(f)
  with self.assertRaises(NativeUIError):
   with f.seams.lock.held():state5.helper_method(h,'begin_quiet_invocation')()
  self.assertEqual([],calls);self.assertEqual(before,self.counts(f))
 def test_metadata_shadow_refused_before_new_reads_or_commands(self):
  f,handle=self.prefix();h=f.owner.state5;calls=[]
  handle.window.previous['source']['feetPosition'][0]+=1
  def foreign():calls.append(True);return 0
  h.metadata_bytes=foreign;before=self.counts(f)
  with self.assertRaises(NativeUIError):
   with f.seams.lock.held():f.owner.capture()
  after=self.counts(f)
  self.assertEqual([],calls);self.assertEqual(before,after)
 def test_foreign_bound_callable_getter_never_runs(self):
  f=self.fixture();h=f.owner.state5;calls=[]
  class Foreign:
   def __getattr__(self,name):calls.append(name);raise AssertionError('No foreign getter')
   def __call__(self,*args):calls.append('call');raise AssertionError('No foreign call')
  h.guard=Foreign();before=self.counts(f)
  with self.assertRaises(NativeUIError):
   with f.seams.lock.held():f.owner.capture()
  self.assertEqual([],calls);self.assertEqual(before,self.counts(f))
 def test_changed_checksum_fallback_function_code_refused(self):
  f,handle=self.prefix();h=f.owner.state5;calls=[];original=quiet.canonical_size
  def foreign(*args):calls.append(True);return 0
  quiet.canonical_size=foreign
  try:
   with self.assertRaises(NativeUIError):quiet.guard_api(h.quiet,h.quiet_api).metadata_bytes()
  finally:quiet.canonical_size=original
  self.assertEqual([],calls)
 def test_gc_disabled_packet_stage_dies_while_actual_two_copies_remain_charged(self):
  import gc,weakref
  f=self.fixture();h=f.owner.state5;stages=[];observed=[];old=sys.getprofile();enabled=gc.isenabled()
  construct=state5.OriginalGraph5.__init__.__code__;step=state5.LifecycleBackgroundState5.quiet_step.__code__
  def profile(frame,event,value):
   if event=='return' and frame.f_code is construct:
    stage=frame.f_locals['self'];stages.append((weakref.ref(stage),id(stage.source)))
   if event=='return' and frame.f_code is step and type(value) is tuple:
    handle=value[1];row=frame.f_locals['row'];same=[ref for ref,source in stages if source==id(row)]
    self.assertEqual(2,len(same));self.assertIs(handle.stage,same[0]());self.assertIsNone(same[1]())
    self.assertIsNot(handle.anchor.original,handle.window.previous)
    self.assertIsNone(handle.stage.result);self.assertEqual(3*handle.seal[5]+6*65536,handle.stage.reserve)
    observed.append(handle);raise NativeUIError('Intentional GC-disabled quiet boundary')
  try:
   gc.disable();sys.setprofile(profile)
   with self.assertRaises(NativeUIError):f.owner.run_owned()
  finally:
   sys.setprofile(old)
   if enabled:gc.enable()
  self.assertEqual(1,len(observed));self.assertIsNone(h.quiet.active)

 def test_actual_after_anchor_copy_failure_keeps_original_partials_and_zero_next_sdk(self):
  f=self.fixture();h=f.owner.state5;copied=[];old=sys.getprofile();code=AvatarDisplacement.__init__.__code__
  def profile(frame,event,value):
   request=h.quiet.active
   if event=='return' and frame.f_code is code and request is not None and request.created and frame.f_locals.get('self') is request.handle.anchor and 'original' in vars(request.handle.anchor):
    copied.append(request.handle.anchor);raise OSError('Actual after-copy injected failure')
  try:
   sys.setprofile(profile)
   with self.assertRaises(NativeUIError):f.owner.run_owned()
  finally:sys.setprofile(old)
  self.assertEqual(1,len(copied));request=h.quiet.active
  self.assertIs(request.handle.anchor,copied[0]);self.assertIsNotNone(request.handle.anchor.original)
  self.assertIsNone(request.handle.window);self.assertIsNotNone(request.stage.source)
  self.assertTrue(h.failed);self.assertTrue(f.bank.failed)
  before=f.bank.archive.state['reads'],len(f.seams.history.commands)
  with self.assertRaises(NativeUIError):
   with f.seams.lock.held():f.owner.capture()
  self.assertEqual(before,(f.bank.archive.state['reads'],len(f.seams.history.commands)))
 def test_full_bank_refusal_before_quiet_decode_keeps_actual_row_and_reservation(self):
  # Obtain a genuine first returned row through the same normal flow; no fake packet.
  f=self.fixture();h=f.owner.state5;old=sys.getprofile();step=state5.LifecycleBackgroundState5.quiet_step.__code__;seen=[]
  def profile(frame,event,value):
   if event=='return' and frame.f_code is step and type(value) is tuple:
    seen.append((frame.f_locals['row'],value[1],frame.f_locals['invocation']));raise NativeUIError('Intentional first original boundary')
  try:
   sys.setprofile(profile)
   with self.assertRaises(NativeUIError):f.owner.run_owned()
  finally:sys.setprofile(old)
  self.assertEqual(1,len(seen));row,handle,invocation=seen[0];bill=f.bank.other_bill
  before=f.bank.archive.state['reads'],len(f.seams.history.commands)
  def exhausted():
   value=bill();value['decodedBytes']=16*1024*1024;return value
  with self.assertRaises(NativeUIError):
   with f.seams.lock.held(),patch.object(f.bank,'other_bill',exhausted):h.quiet_step(row,handle,invocation,'quiet')
  self.assertIs(h.quiet.active.row,row);self.assertIs(h.quiet.active.stage.source,row)
  self.assertIn(h.quiet.active.stage,h.held);self.assertGreater(h.quiet.active.stage.reserve,0)
  self.assertTrue(h.failed);self.assertTrue(f.bank.failed)
  self.assertEqual(before,(f.bank.archive.state['reads'],len(f.seams.history.commands)))

 def test_foreign_class_new_is_bypassed_in_isolated_original_fixture_process(self):
  # Admit the same actual lazy fixture imports before pinning child sources.
  self.fixture()
  before=_loaded_sources();root=Path(__file__).resolve().parents[3]
  environment=dict(os.environ)
  environment['PYTHONPATH']=os.pathsep.join((str(root/'tests/device'),str(root/'android/vr/pico/tests/device')))
  code='from self_tests.test_pico_lifecycle_quiet_step5 import _isolated_constructor_counter; _isolated_constructor_counter()'
  result=subprocess.run([sys.executable,'-u','-c',code],cwd=root,env=environment,
      stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
  self.assertEqual(0,result.returncode,result.stderr.decode('utf-8','replace'))
  self.assertLessEqual(len(result.stdout),262144)
  report=json.loads(result.stdout);self.assertEqual(0,report['foreignCalls'])
  self.assertEqual(1,report['actualWindows']);self.assertEqual([],report['changedSources'])
  self.assertTrue(report['sources'])
  for name,stamp in report['sources'].items():
   self.assertIn(name,before);self.assertEqual(before[name],stamp)
  self.assertEqual(before,_loaded_sources())


 def test_original_bank_close_refuses_helper_shadow_without_foreign_callback_or_false_success(self):
  from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
  f=self.fixture();helper=f.owner.state5;calls=[]
  def foreign():calls.append(True);return True
  helper.close_host=foreign;before=self.counts(f)
  closed=f.bank.close_host()
  self.assertEqual([],calls);self.assertFalse(closed)
  self.assertTrue(any(owner is f.bank for _path,owner in UNRESOLVED))
  self.assertEqual(before,self.counts(f))

def _stamp(path):
 stat=path.lstat()
 return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=[stat.st_dev,stat.st_ino,stat.st_mode,stat.st_uid,stat.st_nlink,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns])

def _loaded_sources():
 root=Path(__file__).resolve().parents[3];result={}
 for module in tuple(sys.modules.values()):
  filename=getattr(module,'__file__',None)
  if filename:
   path=Path(filename).resolve()
   if path.is_relative_to(root) and path.is_file():result[str(path)]=_stamp(path)
 return result

def _isolated_constructor_counter():
 from adapters.pico4.lifecycle_drive import AvatarDisplacement
 before=_loaded_sources();fixture=fixture_module.LifecycleBackgroundState5Tests()
 calls=[];observed=[];installed=False;previous=sys.getprofile()
 try:
  fixture.setUp();fixture.prepare()
  observe=quiet.QuietBook5.observe.__code__;step=state5.LifecycleBackgroundState5.quiet_step.__code__
  def foreign(cls,*args,**kwargs):calls.append(True);raise AssertionError('Foreign constructor callback')
  def profile(frame,event,value):
   nonlocal installed
   if event=='call' and frame.f_code is observe:
    AvatarDisplacement.__new__=staticmethod(foreign);installed=True
   if event=='return' and frame.f_code is step and type(value) is tuple:
    handle=value[1]
    if handle.anchor.original is None or handle.window.previous is None:raise AssertionError('No actual drive copies')
    observed.append(handle);raise NativeUIError('Intentional isolated quiet constructor boundary')
  sys.setprofile(profile)
  try:fixture.owner.run_owned()
  except NativeUIError:pass
  else:raise AssertionError('Expected explicit first-quiet boundary')
 finally:
  sys.setprofile(previous)
  if installed:del AvatarDisplacement.__new__
  fixture.doCleanups()
 if not installed or calls or len(observed)!=1:raise AssertionError('Constructor isolation counter failed')
 after=_loaded_sources();changed=[name for name,stamp in after.items() if name in before and before[name]!=stamp]
 print(json.dumps(dict(foreignCalls=len(calls),actualWindows=len(observed),changedSources=changed,sources=after)),flush=True)
