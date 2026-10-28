"""Passive test-only originals of actual host HID session call boundaries.

No endpoint/selector/expected result is exported. Weak host-object observations
and returned Python calls cannot authenticate or retire the remote transport.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import asyncio,os,time,uuid,weakref
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.assets_model_origin import identity,stamp,ordered

VERSION=1
KINDS={'rsd','receiver','drain','display','hid'}
EDGES={'source-entered','receiver-bound','drain-created','display-entered','stream-start-entered','stream-start-returned',
    'hid-entered','yield-resumed','hid-context-exit-returned','stream-stop-entered','stream-stop-returned',
    'display-context-exit-returned','drain-cancel-entered','drain-cancel-returned','drain-await-settled',
    'receiver-close-entered','receiver-close-returned','source-finally-body-tail-observed'}
UNAVAILABLE=('authenticatedTransportAvailable','tunnelInventoryAvailable','nativeStreamAbsenceAvailable',
    'sdkResourceRetirementAvailable','nativeContactReleaseAvailable','wholeLifecycleRetirementAvailable')


class TouchResourceObservation:
    """No object is strongly retained, and metadata failure cannot skip cleanup."""
    def __init__(self,rsd):
        self.instance=uuid.uuid4().hex;self.birth=time.monotonic_ns();self.events=[];self.resources=[];self.failed=False
        self._refs={};self._worker=weakref.ref(asyncio.current_task());self._loop=weakref.ref(asyncio.get_running_loop())
        self.watch('rsd',rsd)
    def clock(self):return dict(epochMs=time.time_ns()//1000000,monotonicMs=(time.monotonic_ns()-self.birth)//1000000)
    def current(self):
        try:return asyncio.get_running_loop() is self._loop() and asyncio.current_task() is self._worker()
        except RuntimeError:return False
    def edge(self,name):
        try:
            need(self.current() and name in EDGES and len(self.events)<64 and not any(row['edge']==name for row in self.events))
            self.events.append(dict(sequence=len(self.events)+1,edge=name,clock=self.clock()))
        except Exception:self.failed=True
    def watch(self,kind,actual):
        try:
            need(self.current() and kind in KINDS and kind not in self._refs and actual is not None)
            ref=weakref.ref(actual)
            self._refs[kind]=ref;self.resources.append(dict(id=uuid.uuid4().hex,kind=kind,born=self.clock()))
        except Exception:self.failed=True
    def snapshot(self):
        # Capture may run in the retained owner's caller task on the same loop;
        # it does not require (or impersonate) the original worker task.
        need(asyncio.get_running_loop() is self._loop());rows=[]
        for resource in self.resources:
            actual=self._refs[resource['kind']]();row=dict(deepcopy(resource),alive=actual is not None,taskDone=None,taskCancelled=None)
            if resource['kind']=='drain' and actual is not None:
                need(isinstance(actual,asyncio.Task) and actual.get_loop() is self._loop())
                row.update(taskDone=actual.done(),taskCancelled=actual.cancelled())
            rows.append(row);actual=None
        worker=self._worker();value=dict(iosLifecycleTouchResourcesVersion=1,instance=self.instance,hostProcessId=os.getpid(),
            clockDomain='host-loop-touch-resources',clock=self.clock(),complete=not self.failed,
            events=deepcopy(self.events),resources=rows,workerAlive=worker is not None,
            workerDone=worker.done() if worker is not None else None,workerCancelled=worker.cancelled() if worker is not None else None,
            **{key:False for key in UNAVAILABLE})
        validate(value);return value


def validate(value,previous=None):
    exact(value,{'iosLifecycleTouchResourcesVersion','instance','hostProcessId','clockDomain','clock','complete','events','resources',
        'workerAlive','workerDone','workerCancelled'}|set(UNAVAILABLE))
    need(type(value['iosLifecycleTouchResourcesVersion']) is int and value['iosLifecycleTouchResourcesVersion']==1
        and integer(value['hostProcessId'],1) and value['clockDomain']=='host-loop-touch-resources'
        and type(value['complete']) is bool and all(value[key] is False for key in UNAVAILABLE))
    identity(value['instance']);stamp(value['clock']);need(type(value['events']) is list and len(value['events'])<=64
        and type(value['resources']) is list and len(value['resources'])<=5)
    seen=set();old=None
    for index,row in enumerate(value['events'],1):
        exact(row,{'sequence','edge','clock'});need(type(row['sequence']) is int and row['sequence']==index and row['edge'] in EDGES and row['edge'] not in seen)
        seen.add(row['edge']);stamp(row['clock']);ordered(row['clock'],value['clock'])
        if old is not None:ordered(old,row['clock'])
        old=row['clock']
    kinds=set();ids=set()
    for row in value['resources']:
        exact(row,{'id','kind','born','alive','taskDone','taskCancelled'});identity(row['id']);stamp(row['born']);ordered(row['born'],value['clock'])
        need(row['kind'] in KINDS and row['kind'] not in kinds and row['id'] not in ids and type(row['alive']) is bool)
        kinds.add(row['kind']);ids.add(row['id'])
        if row['kind']=='drain' and row['alive']:
            need(type(row['taskDone']) is bool and type(row['taskCancelled']) is bool and (not row['taskCancelled'] or row['taskDone']))
        else:need(row['taskDone'] is None and row['taskCancelled'] is None)
    need(type(value['workerAlive']) is bool)
    if value['workerAlive']:
        need(type(value['workerDone']) is bool and type(value['workerCancelled']) is bool and (not value['workerCancelled'] or value['workerDone']))
    else:need(value['workerDone'] is None and value['workerCancelled'] is None)
    if previous is not None:
        validate(previous);need(value['instance']==previous['instance'] and value['hostProcessId']==previous['hostProcessId']
            and (previous['complete'] or not value['complete']) and len(value['events'])>=len(previous['events'])
            and same(previous['events'],value['events'][:len(previous['events'])]) and len(value['resources'])>=len(previous['resources']))
        ordered(previous['clock'],value['clock'])
        for a,b in zip(previous['resources'],value['resources']):
            need(all(same(a[key],b[key]) for key in ('id','kind','born')) and (a['alive'] or not b['alive']))
            if a['alive'] and b['alive'] and a['taskDone'] is not None:
                need(not a['taskDone'] or b['taskDone']);need(not a['taskCancelled'] or b['taskCancelled'])
        need(previous['workerAlive'] or not value['workerAlive'])
        if previous['workerAlive'] and value['workerAlive']:
            need(not previous['workerDone'] or value['workerDone']);need(not previous['workerCancelled'] or value['workerCancelled'])
    return value
