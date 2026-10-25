"""Keep actual Avatar role finalization ahead of canonical SDK teardown."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
import time
from adapters.native_feature_observation import need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import unpack
from feature_journeys.contract import identifier
from ios.adapters.avatar_finalization import _FIXED,_SUBJECT
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_session_carriers import configured_roots,scoped,covered

_ACTIVE=ContextVar('ios_avatar_session_retirement_budget',default=None)


class Budget:
    def __init__(self,monotonic,started):
        need(callable(monotonic) and number(started,0,1e15))
        self.monotonic,self.last,self.deadline,self.failed=monotonic,started,started+60,False
    def check(self):
        now=self.monotonic()
        if self.failed or not number(now,self.last,self.deadline) or now>=self.deadline:
            self.failed=True;raise NativeUIError('Avatar session retirement deadline exhausted or host clock changed')
        self.last=now


@contextmanager
def budget(adapter,selector,*,monotonic,started=None):
    previous=_ACTIVE.get()
    if previous is not None and previous[0] is adapter and previous[1]==selector:
        previous[2].check();yield previous[2];previous[2].check();return
    owner=Budget(monotonic,monotonic() if started is None else started);token=_ACTIVE.set((adapter,selector,owner))
    try:
        with transport_scope(owner.check):owner.check();yield owner;owner.check()
    finally:_ACTIVE.reset(token)


def read(directory,name):return PrivateFeatureState(directory/name).read()


def fixed_absent(directory,role):
    names=['ios-avatar-'+role+'-'+suffix+'.json' for suffix in _FIXED+_SUBJECT[:4]+('feature','session-quiet')]
    names+=['ios-avatar-'+role+'-'+subject+'-'+suffix+'.json' for subject in ('primary','actor') for suffix in _SUBJECT[4:7]]
    if any(read(directory,name) is not None for name in names):return False
    if role=='actor':
        return not any(directory.glob('phase-publication-avatar-people-*-actor.json')) and not any(directory.glob('phase-retirement-avatar-people-*-actor.json'))
    return all(read(directory,'ios-avatar-primary-actor-'+suffix+'.json') is None for suffix in ('scene','complete'))


def foreign_absent(directory,role):
    other='actor' if role=='primary' else 'primary'
    names=['ios-avatar-'+other+'-'+suffix+'.json' for suffix in _SUBJECT[:4]+('pointers',)]
    names+=['ios-avatar-'+other+'-'+role+'-'+suffix+'.json' for suffix in _SUBJECT[4:7]]
    return all(read(directory,name) is None for name in names)


def owned(adapter,selector):
    directory=adapter.state_path(selector).parent
    from ios.adapters.feature_configuration import configuration
    explicit=configured_roots(configuration(),target=selector);roots={directory}|explicit
    if directory.exists():
        if any(not fixed_absent(directory,role) for role in ('primary','actor')):return True
        if any(directory.glob('ios-avatar-*-*-finalization.json')):return True
    return bool(scoped(directory,roots,explicit=bool(explicit)))


def session_entry(function,*,monotonic=time.monotonic):
    @wraps(function)
    def invoke(adapter,selector):
        started=monotonic()
        if not owned(adapter,selector):return function(adapter,selector)
        with budget(adapter,selector,monotonic=monotonic,started=started):return function(adapter,selector)
    return invoke


def ensure_finalized(adapter,selector,*,monotonic=time.monotonic,sleep=time.sleep):
    started=monotonic()
    if not owned(adapter,selector):return True
    with budget(adapter,selector,monotonic=monotonic,started=started) as work:
        directory=adapter.state_path(selector).parent
        from ios.adapters.feature_configuration import configuration,reader
        config=configuration();explicit=configured_roots(config,target=selector);roots={directory}|explicit;members=set();complete=[];pending=[]
        def qualify(path,value):
            from ios.adapters.avatar_completed_archive import verify
            binding=verify(directory,path,value,check=work.check,membership=members);roots.add(Path(value['artifactRoot']))
            scope={key:item for key,item in binding.items() if key!='processIdentity'}
            adapter._retired_candidate_scope(selector,scope)
            installed=adapter._binding_store(selector).read()
            if installed is not None:need(installed['scope']==scope and installed['process'] is not None and str(installed['process']['pid'])==binding['processIdentity'])
        plans=sorted(directory.glob('ios-avatar-*-*-finalization.json'));need(len(plans)<=64)
        for path in plans:
            value=PrivateFeatureState(path).read();need(value is not None);role=value.get('role');run=identifier(value.get('runId'))
            need(role in ('primary','actor') and path.name=='ios-avatar-'+role+'-'+run+'-finalization.json');rows=unpack(value['payload']);need(len(rows)==1)
            if rows[0].get('phase')=='complete':qualify(path,value);complete.append(role)
            else:pending.append((role,run))
        # The Actor must finish with its explicit admitted Primary selector;
        # canonical teardown cannot guess that target or terminate it early.
        need(read(directory,'ios-avatar-actor-feature.json') is None and not any(role=='actor' for role,_run in pending))
        active=read(directory,'ios-avatar-primary-feature.json');runs={run for role,run in pending if role=='primary'}
        if active is not None:runs.add(identifier(active.get('runId')))
        if runs:
            need(len(runs)==1 and config is not None and 'avatar-people' in config['areas']);run=runs.pop();work.check()
            flow=IOSAvatarRuntime(adapter)._avatar_feature(selector,run,role='primary',client=reader(config),settings=config['avatarPeople'])
            flow.deadline=work.deadline if flow.deadline is None else min(flow.deadline,work.deadline)
            need(flow.finalize()=={'performed':True} and read(directory,'ios-avatar-primary-feature.json') is None)
            path=directory/('ios-avatar-primary-'+run+'-finalization.json');value=PrivateFeatureState(path).read();need(value is not None)
            qualify(path,value);complete.append('primary')
        own='primary' if 'primary' in complete else 'actor';need(complete and fixed_absent(directory,own));work.check()
        waiting=work.monotonic()
        while not foreign_absent(directory,own):
            work.check();need(work.last-waiting<20);sleep(.15);work.check()
        need(fixed_absent(directory,own) and foreign_absent(directory,own));work.check();covered(directory,roots,members);work.check();return True
