"""Keep owned Emote finalization ahead of canonical ordinary process teardown."""
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
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.adapters.emote_session_carriers import configured_roots,scoped,scoped_covered

_FIXED=('marker','marker-files','marker-script','marker-recovery','samples','sample-recovery','observer','native-files',
    'marker-entities','retirement-originals','rendered-retirement-originals','keyed-retirement-originals','restoration-frames','pointers','keys')
_ACTIVE=ContextVar('ios_emote_session_retirement_budget',default=None)


class Budget:
    def __init__(self,monotonic,started):
        need(callable(monotonic) and number(started,0,1e15))
        self.monotonic,self.started,self.last,self.deadline,self.failed=monotonic,started,started,started+60,False
    def check(self):
        now=self.monotonic()
        if self.failed or not number(now,self.last,self.deadline) or now>=self.deadline:
            self.failed=True;raise NativeUIError('Emote session retirement deadline exhausted or host clock changed')
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


def fixed_absent(directory):
    names=['ios-emote-'+role+'-'+tail+'.json' for role in ('primary','actor') for tail in _FIXED]
    names+=['ios-emote-primary-'+tail+'.json' for tail in ('sources','source-recovery','peer-retirement')]
    names+=['ios-emote-'+tail+'.json' for tail in ('inputs','cleanup-inputs','background','actor-peer-sources','actor-peer-recovery')]
    if any(read(directory,name) is not None for name in names):return False
    return not any(directory.glob('phase-publication-emotes-*-actor.json')) and not any(directory.glob('phase-retirement-emotes-*-actor.json'))


def foreign_sources_absent(directory):
    # These are the independent Actor's fixed-channel originals, physically in
    # this Primary SDK directory. Only their actual owner may retire them.
    return all(read(directory,'ios-emote-actor-'+tail+'.json') is None for tail in ('sources','source-recovery'))


def owned(adapter,selector):
    directory=adapter.state_path(selector).parent
    from ios.adapters.feature_configuration import configuration
    explicit=configured_roots(configuration(),target=selector);roots={directory}|explicit
    if directory.exists():
        if any(read(directory,'ios-emote-'+role+'-feature.json') is not None for role in ('primary','actor')):return True
        if not fixed_absent(directory) or not foreign_sources_absent(directory) or any(directory.glob('ios-emote-*-*-finalization.json')):return True
    return bool(scoped(directory,roots,explicit=bool(explicit)))


def session_entry(function,*,monotonic=time.monotonic):
    @wraps(function)
    def invoke(adapter,selector):
        started=monotonic()
        # Admission here is read-only host metadata. No SDK/candidate request
        # precedes the original transport guard, even if this scan was slow.
        if not owned(adapter,selector):return function(adapter,selector)
        with budget(adapter,selector,monotonic=monotonic,started=started):return function(adapter,selector)
    return invoke


def ensure_finalized(adapter,selector,*,monotonic=time.monotonic,sleep=time.sleep):
    started=monotonic()
    if not owned(adapter,selector):return True
    with budget(adapter,selector,monotonic=monotonic,started=started) as work:
        runtime=IOSEmoteRuntime(adapter);directory=runtime.state_path(selector).parent
        from ios.adapters.feature_configuration import configuration
        explicit=configured_roots(configuration(),target=selector);roots={directory}|explicit;members=set()
        owners={role:read(directory,'ios-emote-'+role+'-feature.json') for role in ('primary','actor')}
        pending=[];complete_primary=[];plans=sorted(directory.glob('ios-emote-*-*-finalization.json'));need(len(plans)<=64)
        def qualify(path,value):
            from ios.adapters.emote_completed_archive import verify
            binding=verify(directory,path,value,check=work.check,membership=members,report_target=selector)
            roots.add(Path(value['artifactRoot']))
            scope={key:item for key,item in binding.items() if key!='processIdentity'}
            adapter._retired_candidate_scope(selector,scope)
            installed=adapter._binding_store(selector).read()
            if installed is not None:
                need(installed['scope']==scope and installed['process'] is not None
                    and str(installed['process']['pid'])==binding['processIdentity'])
        for path in plans:
            value=PrivateFeatureState(path).read();need(value is not None)
            role=value.get('role');run=identifier(value.get('runId'))
            need(role in owners and path.name=='ios-emote-'+role+'-'+run+'-finalization.json')
            rows=unpack(value['payload']);need(len(rows)==1)
            if rows[0].get('phase')!='complete':pending.append((role,run))
            else:
                qualify(path,value)
                if role=='primary':complete_primary.append(run)
        # The worker has the explicit actual primaryTarget selector. Canonical
        # cleanup must not invent it or stop this Actor's process first.
        need(owners['actor'] is None and not any(role=='actor' for role,_run in pending))
        active=owners['primary'];runs={run for role,run in pending if role=='primary'}
        if active is not None:runs.add(identifier(active.get('runId')))
        if runs:
            need(len(runs)==1)
            from ios.adapters.feature_configuration import configuration,reader
            config=configuration();need(config is not None and 'emotes' in config['areas'])
            run=runs.pop();work.check()
            flow=runtime._emote_feature(selector,run,role='primary',client=reader(config),settings=config['emotes'])
            flow.deadline=work.deadline if flow.deadline is None else min(flow.deadline,work.deadline)
            need(flow.finalize()=={'performed':True} and read(directory,'ios-emote-primary-feature.json') is None)
            plan=read(directory,'ios-emote-primary-'+run+'-finalization.json')
            need(plan is not None and unpack(plan['payload'])[0]['phase']=='complete')
            qualify(directory/('ios-emote-primary-'+run+'-finalization.json'),plan);complete_primary.append(run)
        need(fixed_absent(directory));work.check()
        if not foreign_sources_absent(directory):
            need(complete_primary)
            waiting=work.monotonic()
            # No source lock is held here and no SDK is polled or created.
            # The original 60 s budget remains active through the outer
            # canonical final binding checks and normal terminate/delete.
            while not foreign_sources_absent(directory):
                work.check();need(work.last-waiting<20);sleep(.15);work.check()
        need(fixed_absent(directory));work.check();scoped_covered(directory,roots,members);work.check();return True
