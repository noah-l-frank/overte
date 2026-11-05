# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Three separate fresh normal input boundaries, all asserts outside SourceLock."""
import gc
from adapters.normal_ui import NativeUIError
from adapters.pico4.world_controller_focus import WorldControllerFocus1
from self_tests.pico_world_host_dom_fixture import Fixture,trace

TEXT='Grüße 🌍 漢字'
def setup(artifacts,**flags):
 f=Fixture(artifacts,controller=True,**flags);f.construct();f.factory()
 return f

def normal_controller_focus_ime_new_document(artifacts):
 f=setup(artifacts);r=f.resources;report={};business=None
 try:
  owner=WorldControllerFocus1(r)
  assert r.model.focused is False and r.node.ready['editor']['active'] is False
  assert owner.perform() is True and owner.done and len(owner.transport.envelopes)==1
  assert r.model.focused is True and len(r.old_groups)==1
  assert r.old_groups[0]['focus_call']['request']['operation']=='measure-current-ray'
  assert r.focus_call['request']['operation']=='observe-current-focus'
  assert r.focus.original()['request']['commandId']!=owner.calibration['request']['commandId']
  assert owner.receipt['finishedMonotonic']-owner.receipt['startedMonotonic']>=2
  ime,reader=r.create_ime_sources();reader.arm();ime.commit(TEXT)
  for cursor in range(4):reader.observe(cursor)
  after=r.reader.read(f.context.run,f.context.fixture_url,f.context.owner)
  assert after['source']['dom']['editor']['text']==TEXT and reader.cursor==4
  assert r.event_model.issued is True and r.node.process.poll() is None
  bill=r.census();assert bill['decodedBytes']<=16777216
  report=dict(case='normal_controller_focus_ime_new_document',actualSessionPrimaryEnvelopes=1,
   actualGestureHistoricalReceipt=True,actualCompiledControllerPrototype=True,normalPointerModel=True,
   freshIndependentFocus=True,issuedUnicodeOnce=True,newOriginalDocumentText=after['source']['dom']['editor']['text'],
   rawReceipts=r.raw.state['reads'],controllerSourceStateCopies=len(owner.rows),globalBill=bill,
   sourceModel='DECLARED_HOST',nativeQtDeviceQualified=False,stereoQualified=False,wholeClaim=False)
 except BaseException as error:business=error;r.fail(error);raise
 finally:
  try:report['knownHostCloses']=f.close()
  except BaseException:
   if business is None:raise
 assert all(report['knownHostCloses']);return report

def controller_no_effect(artifacts):
 f=setup(artifacts,no_effect=True);r=f.resources;report={};business=None
 try:
  owner=WorldControllerFocus1(r)
  assert owner.perform() is False and owner.done is False
  assert len(owner.transport.envelopes)==1 and owner.receipt is not None
  assert r.focus.last['source']['nativeEditor']['focused'] is False
  assert r.model.focused is False and r.event_owner is None
  assert r.node.last['value']['editor']['focused'] is False
  before=r.raw.state['reads'];factory_refused=False;gate_error_id=None
  try:r.create_ime_sources()
  except NativeUIError as error:factory_refused=True;gate_error_id=id(error)
  gc.collect()
  assert factory_refused and r.event_owner is r.trace_reader is r.intent is None
  assert r.raw.state['reads']==before and r.failure is not None and id(r.failure[0])==gate_error_id and r.failure[1] is not None
  refused=False
  try:owner.perform()
  except NativeUIError:refused=True
  assert refused and r.raw.state['reads']==before and len(owner.transport.envelopes)==1 and r.event_owner is None
  # No independent focus => caller refuses BEFORE arm/IME/input, ACK not effect.

  report=dict(case='controller_no_effect',actualSessionPrimaryEnvelopes=1,independentFocusFalse=True,
   newImeInputs=0,actualImeFactoryRefusedBeforeAllocations=True,firstGateTBRetained=True,noInputReplay=True,rawReceipts=r.raw.state['reads'],nativeQtDeviceQualified=False,wholeClaim=False)
 except BaseException as error:business=error;r.fail(error);raise
 finally:
  try:report['knownHostCloses']=f.close()
  except BaseException:
   if business is None:raise
 assert all(report['knownHostCloses']);return report

def controller_foreign_scene(artifacts):
 f=setup(artifacts,foreign=True);r=f.resources;report={};business=None
 try:
  owner=WorldControllerFocus1(r);found=False;error_id=None
  try:owner.perform()
  except NativeUIError as error:found=True;error_id=id(error)
  gc.collect()
  assert found and r.failure is not None and owner.failure is not None
  assert r.failure[1] is not None and owner.failure[1] is not None
  assert len(owner.transport.envelopes)==0 and r.event_owner is None
  assert r.focus_call['raw_ref'] is not None and r.raw.state['reads']==4
  assert r.model.focused is False and not r.compound['done']
  chain=trace(r.failure[0]);frames=[f for row in chain for f in row['frames']]
  assert any(f['source'].endswith('/world_browser_ray.py') and f['name'] in ('ray','validate') for f in frames)
  before=r.raw.state['reads'];again=False
  try:owner.perform()
  except NativeUIError:again=True
  assert again and r.raw.state['reads']==before and len(owner.transport.envelopes)==0
  report=dict(case='controller_foreign_scene',actualRawBeforeSceneRefusal=True,rawReceipts=4,
   actualSessionPrimaryEnvelopes=0,newImeInputs=0,noInputReplay=True,firstOwnerTB=trace(r.failure[0]),
   nativeQtDeviceQualified=False,wholeClaim=False)
 except BaseException as error:business=error;r.fail(error);raise
 finally:
  try:report['knownHostCloses']=f.close()
  except BaseException:
   if business is None:raise
 assert all(report['knownHostCloses']);return report
