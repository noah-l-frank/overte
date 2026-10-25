"""Whole Avatar metadata retirement after original inactive fixture input.

The ordinary scene and both account retirements must already be complete.
This final host stage never reopens a World or repeats a product input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack,same
from ios.adapters.avatar_final_archive import IOSAvatarFinalArchive
from ios.adapters.avatar_session_quiet import IOSAvatarSessionQuiet
from ios.adapters.emote_native_prefix import follow

_FIXED=('marker','marker-files','marker-script','marker-recovery','samples','sample-recovery','observer',
    'marker-entities','file-receipts','scene','restoration-frames','pointers','actions','consent','inputs','input-reads',
    'cleanup-controls','cleanup-inputs','login','account-origin','account-probe','private-login-input','final')
_SUBJECT=('sources','source-recovery','peer-sources','peer-recovery','account-reads','postlogout','postlogout-tail','pointers')


class AvatarFinalization:
    def __init__(self,flow):
        self.flow=flow;self.store=PrivateFeatureState(flow.store.path.with_name('ios-avatar-'+flow.role+'-'+flow.run+'-finalization.json'))
        self.live_final=None
    def path(self,name,subject=None):
        f=self.flow;selector=f.selector if subject is None else f.selectors[subject]
        return PrivateFeatureState(f.runtime.state_path(selector).with_name(name))
    def paths(self,read=None):
        f=self.flow;read=(lambda store:store.read()) if read is None else read
        result=[self.path('ios-avatar-'+f.role+'-'+name+'.json') for name in _FIXED]
        for subject in ('primary','actor'):
            result.extend(self.path('ios-avatar-'+f.role+'-'+suffix+'.json',subject) for suffix in _SUBJECT[:4])
            result.extend(self.path('ios-avatar-'+f.role+'-'+subject+'-'+suffix+'.json',subject) for suffix in _SUBJECT[4:7])
            result.append(self.path('ios-avatar-'+f.role+'-pointers.json',subject))
            result.append(self.path('ios-avatar-'+f.role+'-'+subject+'-surface.json',subject))
        if f.role=='actor':
            result.extend(self.path(prefix+'-avatar-people-'+f.run+'-actor.json') for prefix in ('phase-publication','phase-retirement'))
        else:result.extend(self.path('ios-avatar-primary-actor-'+suffix+'.json') for suffix in ('scene','complete'))
        samples=read(self.path('ios-avatar-'+f.role+'-samples.json'))
        if samples is not None:
            for row in unpack(samples['payload'])[0]['rows']:
                result.append(self.path('graphics-world-frame-'+f.role+'-0-'+row['requestId'][4:]+'.json'))
        restoration=read(self.path('ios-avatar-'+f.role+'-restoration-frames.json'))
        if restoration is not None:
            from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
            owner=IOSAvatarRestorationFrames.archive(restoration,store=self.path('ios-avatar-'+f.role+'-restoration-frames.json'),root=f.root,
                binding=f.state['bindings'][f.role],run=f.run,role=f.role,lock=f.lock)
            need(owner.state['pending'] is None)
            for reference in owner.state['records']:
                original=owner.original(reference);result.append(self.path('graphics-world-frame-'+f.role+'-0-'+original['requestId'][4:]+'.json'))
        result.append(self.path('ios-avatar-'+f.role+'-session-quiet.json'));result.append(f.store)
        # A pointer owner may occur in both the own-role and subject lists.
        return list({str(store.path):store for store in result}.values())
    def guard(self):
        f=self.flow
        for lock in f.locks.values():lock.assert_held()
        f.clock();actual=f.runtime._sources(f.selector);need(same(actual['binding'],f.state['bindings'][f.role]) and actual['check']() is not False)
        return True
    def quiet_owner(self):
        f=self.flow;need(self.live_final is not None)
        return IOSAvatarSessionQuiet(self.path('ios-avatar-'+f.role+'-session-quiet.json'),f.root,f.state['bindings'][f.role],f.run,f.role,
            f.lock,self.local_guard,lambda:self.live_final.factory(f.role),f.phase,self.live_final.inputs[f.role],epoch_ms=f.epoch_ms,monotonic=f.monotonic)
    def local_guard(self):
        f=self.flow;f.lock.assert_held();f.cleanup_deadline();actual=f.runtime._sources(f.selector)
        need(same(actual['binding'],f.state['bindings'][f.role]) and actual['check']() is not False);return True
    def decode(self,copies):
        f=self.flow;need(str(f.store.path) in copies);raw=copies[str(f.store.path)];need(raw is not None)
        from ios.adapters.avatar_feature import IOSAvatarFeature
        historical=IOSAvatarFeature.archive(f.runtime,raw,f.client,f.locks)
        need(historical.state['phase']=='cleaned' and historical.role==f.role and same(historical.state['bindings'],f.state['bindings'])
            and historical.state['phaseInstance']==f.state['phaseInstance'])
        expected=self.paths(lambda store:copies[str(store.path)])
        need(list(copies)==[str(store.path) for store in expected]);proof=historical.completed_original()
        # The current inactive stage adds no public baseline or retirement fact.
        # Its own SDK originals follow the actual pre-DELETE whole completion.
        own=historical.role;final_event=next(row for row in historical.state['cleanup'] if row['kind']==('complete-publication' if own=='actor' else 'final-ready'))
        final=historical.final_owner(value=historical.kept(final_event['owner']));last=final.group(final.record(final_event['references'][-1]))[own]
        value=copies[str(self.path('ios-avatar-'+own+'-session-quiet.json').path)];need(value is not None)
        quiet=IOSAvatarSessionQuiet.archive(value,store=self.path('ios-avatar-'+own+'-session-quiet.json'),root=f.root,
            binding=f.state['bindings'][own],run=f.run,role=own,lock=f.lock,inputs=final.inputs[own])
        need(quiet.state['pending'] is None);references=[row['reference'] for row in quiet.state['records'] if row['reference'] is not None]
        current=quiet.quiet(references);first=quiet.original(quiet.record(references[0]));follow(last['right']['clockJoin']['nativeAfter'],first['left']['clockJoin']['nativeBefore'])
        need(current['phase']['instance']==f.state['phaseInstance'] and current['phase']['activations'][-1]['ticket']==proof['ticket'])
        for name in ('account-origin','account-probe','private-login-input'):
            need(copies[str(self.path('ios-avatar-'+own+'-'+name+'.json').path)] is None)
        return dict(iosAvatarFinalizationProofVersion=1,runId=f.run,role=own,binding=f.state['bindings'][own],quiet=current,
            wholeOriginalSha256=proof['retirement']['originalSha256'])
    def transaction(self):
        f=self.flow;saved=self.store.read()
        paths=self.paths() if saved is None else [PrivateFeatureState(path) for path in saved['paths']]
        return IOSAvatarFinalArchive(self.store,f.root,f.state['bindings'][f.role],f.run,f.role,f.locks,paths,self.guard,self.decode)
    def finish(self):
        f=self.flow
        # Source samplers need a current independent passive read budget. The
        # old ordinary cleanup recipe deadline is never renewed or consulted
        # for new input; this path contains no normal product input at all.
        from ios.adapters import avatar_operation_clock
        old=getattr(f,'final_read_clock',None);f.final_read_clock=avatar_operation_clock.begin(f.epoch_ms(),f.monotonic())
        try:
            with f.held(paired=True):
                f.load();saved=self.store.read()
                if f.state is None and saved is not None:
                    # Fixed coordinator metadata is the last CAS retirement.
                    # Its actual immutable copy is sufficient after a lost
                    # return; no SDK session or product state is recreated.
                    transaction=IOSAvatarFinalArchive(self.store,saved['artifactRoot'],saved['binding'],f.run,f.role,f.locks,
                        [PrivateFeatureState(path) for path in saved['paths']],self.guard,self.decode)
                    need(transaction.state['phase'] in ('retiring','complete') and len(transaction.state['records'])==len(transaction.paths))
                    raw=transaction.copies()[str(f.store.path)]
                    from ios.adapters.avatar_feature import IOSAvatarFeature
                    historical=IOSAvatarFeature.archive(f.runtime,raw,f.client,f.locks)
                    need(historical.role==f.role and same(historical.selectors,f.selectors) and historical.root==f.root and same(historical.policy,f.policy))
                    f.state=deepcopy(historical.state)
                need(f.state is not None and f.state['phase']=='cleaned');status=f.phase.status();need(not status['active'])
                transaction=self.transaction()
                if transaction.state is not None:return transaction.retire()
                f.completed_original();self.live_final=f.final_owner()
            for _ in range(40):
                with f.held():
                    owner=self.quiet_owner();owner.recover();owner.capture();refs=[row['reference'] for row in owner.state['records'] if row['reference'] is not None]
                    if len(refs)>=3:
                        first,last=owner.record(refs[0]),owner.record(refs[-1])
                        if last['acquisition']['hostBeforeMonotonic']-first['acquisition']['hostAfterMonotonic']>=3:
                            owner.quiet(refs);owner.fresh(last);break
                f.sleep(.2)
            else:raise ValueError('Own original SDK did not establish post-fixture-retirement quiet')
            with f.held(paired=True):
                f.load();status=f.phase.status();need(not status['active'])
                transaction=self.transaction();need(transaction.state is None);transaction.begin(status);return transaction.retire()
        finally:f.final_read_clock=old
