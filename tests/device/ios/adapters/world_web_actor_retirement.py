"""Independent actor's actual passive SDK inventories and post-close quiet.

Primary file/GPU/pixel retirement remains the primary's separate original
receipt. This owner reads the real primary SDK and the actor's own SDK; it
accepts no normalized primary publication as a native resource outcome.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager,ExitStack
from contextvars import ContextVar
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.world_web_observer import WorldWebObserver
from ios.adapters.world_web_retired import quiet,quiet_summary,activity
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_history import current_view
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
from ios.adapters import create_entities,world_web_keys,world_web_source,pointer_state,world_web_surface_lease
from ios.adapters.world_web_resource_disposition import disposition
from ios.adapters.world_web_scene import scene
from ios.adapters.world_web_original_membership import OriginalMembership

_ORIGINALS=ContextVar('world_web_actor_retirement_originals',default=None)


class WorldWebActorRetirement:
    def __init__(self,store,observer,*,sleep=time.sleep):
        need(isinstance(store,PrivateFeatureState) and isinstance(observer,WorldWebObserver) and observer.role=='actor' and callable(sleep))
        self.store,self.observer,self.sleep=store,observer,sleep
        self.source,self.peer,self.lock,self.run,self.binding=observer.source,observer.peer,observer.lock,observer.run,deepcopy(observer.binding);self.role='actor'
        self.lock.assert_held();self.source.lock.assert_held();self.previous=store.read();self.state=dict(phase='new',ticket=None,records=[],quiet=[])
        if self.previous is not None:self.state=self.decode(self.previous)
    def envelope(self,state):return dict(iosWorldWebActorRetirementVersion=1,binding=self.binding,runId=self.run,payload=pack([state]))
    def save(self):
        self.lock.assert_held();self.source.lock.assert_held();need(same(self.store.read(),self.previous));value=self.envelope(self.state)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def entry(self,original):
        self.observer.validate_original(original);return self.observer.entries()[original['reference']['index']-1]
    def measure(self,original):
        with self.observer.validation_round():
            self.observer.round_guard();result=deepcopy(self._historical_frames(original));self.observer.round_guard();return result
    def _historical_frames(self,original):
        """Private immutable historical projection, inside the guarded decoder.

        This borrowed value never escapes a public method or a callback. The
        enclosing complete decoder checks the actual inventories on entry and
        exit. Native quiet, current candidate and final freshness are not memoized.
        """
        need(self.observer._round is not None)
        cache=self.observer._round.setdefault('actorRetirement',{})
        key=digest([original,self.state,self.previous,self.observer.round_header(),
            self.source._round[0],self.peer._round[0],None if self.observer.lease is None else self.observer.lease.packet()])
        if key in cache and cache[key][1].matches():return cache[key][0]
        context=_ORIGINALS.get();proofs=None if context is None else context['frames'];borrowed=False
        if proofs is not None and self.source._write_round is None and self.peer._write_round is None:
            proof_key,entry=self.frame_proof_key(original);self.observer.round_guard()
            if proof_key in proofs and proofs[proof_key].matches():
                # Current readonly Source rounds have revalidated the complete
                # byte graph. Borrow their private originals only inside this
                # same guarded round; measure() still copies every public
                # return. No frame/clock/current verdict lives in the API memo.
                from ios.adapters.world_web_sources import WorldWebSources
                if all(getattr(owner.frame,'__func__',None) is WorldWebSources.frame for owner in (self.source,self.peer)):
                    result=self.source._round[2][entry['source']['index']-1],self.peer._round[2][entry['peer']['index']-1];borrowed=True
                else:result=self._measure(original)
            else:
                result=self._measure(original)
                if proof_key in proofs or len(proofs)<256:proofs[proof_key]=OriginalMembership()
            self.observer.round_guard()
        else:result=self._measure(original)
        if key in cache or len(cache)<256:
            cache[key]=(result if borrowed else deepcopy(result),OriginalMembership());return cache[key][0]
        return result

    def frame_proof_key(self,original):
        observer=self.observer;need(observer.lease is not None and self.source is observer.source and self.peer is observer.peer)
        exact(original,{'iosWorldWebObservationOriginalVersion','runId','role','binding','reference'})
        need(type(original['iosWorldWebObservationOriginalVersion']) is int and original['iosWorldWebObservationOriginalVersion']==1
            and same(original,observer.original(original['reference'])))
        index=original['reference']['index'];need(type(index) is int and 1<=index<=len(observer.state['records']))
        entry=observer.entries()[index-1]
        def prefix(owner,reference):
            rows=owner._round[1]['records']
            need(reference in rows and type(reference['index']) is int and 1<=reference['index']<=len(rows))
            return rows[:reference['index']]
        value=[original,self.state['ticket'],observer.round_header(),observer.state['records'][:index],
            prefix(self.source,entry['source']),prefix(self.peer,entry['peer']),self.source.version,self.peer.version,
            self.source.historical,self.peer.historical,observer.lease.packet(),observer.lease.scope.previous]
        parsers=tuple(getattr(method,'__func__',method) for method in (self._measure,self.native_frames,self.entry,
            observer._derive,observer.validate_original,self.source.frame,self.peer.frame))
        return (digest(value),parsers),entry
    @contextmanager
    def original_round(self):
        """Pure original-parent DTO reuse; no readonly Source over any write."""
        with ExitStack() as stack:
            from adapters.original_file_reads import scope as read_scope
            # Retain the actual reads already made by this same operation.
            # A later original decode must not start a different census and
            # reread the immutable pre-capture Scope inside the send window.
            # This records only real reads; it adds no inferred member/path.
            stack.enter_context(read_scope())
            if _ORIGINALS.get() is None:
                token=_ORIGINALS.set(dict(originals={},frames={}));stack.callback(_ORIGINALS.reset,token)
            from ios.adapters.world_web_scope_archive import original_round
            stack.enter_context(original_round())
            for owner in (self.source,self.peer):stack.enter_context(owner.parts.snapshot.validation_round())
            stack.enter_context(world_web_source.validation_round());yield
    @contextmanager
    def publication_round(self,publisher):
        from ios.adapters.world_web_publication_round import WorldWebPublicationRound
        with WorldWebPublicationRound(self,publisher).held():yield
    def _measure(self,original):
        entry=self.entry(original);need(self.observer.lease is not None)
        b=self.peer.frame(entry['peer']);primary=self.source.frame(entry['source'])
        return self.native_frames(primary,b)
    def native_frames(self,primary,b):
        owned=self.observer.lease.packet();first=self.observer.entries()[0];a=self.peer.frame(first['peer'])
        need(primary['phaseBefore']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}) and primary['ticket']==b['ticket']==self.state['ticket'])
        body_preserved(a['originals']['world'],b['originals']['world']);view_preserved(a['originals']['world'],b['originals']['world'])
        need(same(a['originals']['world']['source']['tree']['entities'],b['originals']['world']['source']['tree']['entities']))
        for packet in (primary,b):
            raw=packet['originals'];world_web_keys.drained(raw['keys']);need(raw['ledgerAfter']['iosWorldWebVersion']>=2
                and current_view(raw['ledgerAfter']) is None and world_web_source.pending(raw['ledgerAfter'])==[] and raw['document'] is None)
            ui=raw['uikit']['observation']['nativeUi'];need(ui['valid'] and not ui['keyboardVisible'] and ui['imeInsetBottom']==0 and not raw['widgets']['tabletShown'])
        pointer_state.drained(a['originals']['pointer'],b['originals']['pointer'],after_epoch=a['clockJoin']['nativeAfter']['capturedEpochMs'])
        before=self.source.frame(owned['before']);pointer_state.drained(before['originals']['pointer'],primary['originals']['pointer'],after_epoch=before['clockJoin']['nativeAfter']['capturedEpochMs'])
        dead=create_entities.retired(primary['originals']['entities'],owned['returned'],after_epoch=owned['admission']['manager']['assignedEpochMs']);need(dead is not None)
        if self.source.version>=5:
            from ios.adapters.world_web_emission_retirement import drained
            drained(primary['originals']['emissions'],dead['id'],owned['admission']['manager'],owned['admission']['code'])
        # Every original WK view must tear down. A cached original QObject
        # may remain alive until the separate role-owned OS retirement proof.
        events=primary['originals']['ledgerAfter']['events'][len(before['originals']['ledgerAfter']['events']):];created={};deaths={}
        for row in events:
            identity=row['identity'];need(identity['sourceIdentity']=='web-entity:'+dead['id']);key=(identity['handle'],identity['creation'])
            if row['kind']=='view-created':need(key not in created);created[key]=[row['sequence'],None]
            elif row['kind']=='view-teardown':need(key in created and created[key][1] is None);created[key][1]=row['sequence']
            elif row['kind']=='owner-destroyed':need(identity['handle'] not in deaths);deaths[identity['handle']]=row['sequence']
        need(created and set(deaths)<={key[0] for key in created} and all(value[1] is not None and value[0]<value[1] for value in created.values()))
        for key,value in created.items():
            if key[0] in deaths:need(value[1]<deaths[key[0]])
        if owned['iosWorldWebLeaseVersion']==2:
            barrier=self.observer.lease.scope_state()['stopBarrier'];need(barrier is not None)
            world_web_surface_lease.retired(owned['surfaceLease'],primary['originals']['surfaces'],after_epoch=barrier['epoch'])
            admitted=self.source.frame(owned['after'])['originals']['closures']
            disposition(primary['originals']['closures'],admitted)
            # No Web marker is created on the independent actor. Its original
            # whole inventories still preserve every unowned context and holder.
            disposition(b['originals']['closures'],a['originals']['closures'],partial=True)
        else:need(set(deaths)=={key[0] for key in created})
        self.observer.lease.current(primary,live=False)
        return primary,b
    def cleanup(self,ticket):
        from feature_journeys.contract import identifier
        identifier(ticket)
        if self.state['ticket'] is None:self.state.update(ticket=ticket,phase='quiet');self.save()
        need(self.state['ticket']==ticket);self.state['phase']='quiet';self.save();started=self.peer.monotonic()
        for _attempt in range(61):
            original,_public=self.observer.capture();qualified=False
            # All following native comparisons are pure reads of this exact
            # captured graph. Keep their existing census/Source/lease round
            # together, ending it before either owner CAS or another capture.
            with self.observer.validation_round():
                current=self.measure(original);candidate=deepcopy(self.state['quiet'])
                if candidate:
                    old=self.measure(candidate[-1])
                    if any(not same(activity(a),activity(b)) for a,b in zip(old,current)):candidate=[]
                candidate.append(original)
                if len(candidate)>=4:
                    first_a,first_b=self.measure(candidate[0]);last_a,last_b=self.measure(candidate[-2])
                    try:quiet(first_a,last_a);quiet(first_b,last_b)
                    except NativeUIError:pass
                    else:qualified=True
            self.state['records'].append(original);self.state['quiet']=candidate;self.save()
            if qualified:self.state['phase']='retired';self.save();return self.original()
            need(self.peer.monotonic()-started<15);self.sleep(.1)
        need(False)
    def qualification(self,state):
        need(state['phase']=='retired' and len(state['quiet'])>=4)
        with self.observer.validation_round():
            frames=[self._historical_frames(original) for original in state['quiet']]
            # The final dual-SDK acquisition follows the completed original
            # quiet interval. Its Primary-before must not overlap the prior
            # Actor-after; an Own-SDK clock is never renamed as Primary time.
            quiet(frames[0][0],frames[-2][0]);quiet(frames[0][1],frames[-2][1])
            quiet(frames[0][0],frames[-1][0]);quiet(frames[0][1],frames[-1][1])
            before=frames[-1][0]['clockJoin'];after=frames[-2][1]['clockJoin']
            need(before['hostBeforeEpochMs']>=after['hostAfterEpochMs'] and before['hostBeforeMonotonic']>=after['hostAfterMonotonic'])
            observed=self.observer.validate_original(state['quiet'][-1]);need(observed['public']['resources']==[] and observed['public']['artifacts']==[])
            return dict(observed,quiet=quiet_summary(frames[0][1],frames[-2][1]))
    def decode(self,value):
        with self.observer.validation_round():return self._decode(value)
    def _decode(self,value):
        exact(value,{'iosWorldWebActorRetirementVersion','binding','runId','payload'});rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','ticket','records','quiet'});need(state['phase'] in ('new','quiet','retired') and len(state['records'])<=96)
        need(type(state['quiet']) is list and all(original in state['records'] for original in state['quiet'])
            and [original['reference']['index'] for original in state['quiet']]==sorted({original['reference']['index'] for original in state['quiet']}))
        previous=self.state;self.state=state
        try:
            prior=None
            for original in state['records']:
                self._historical_frames(original)
                if prior is not None:need(original['reference']['index']>prior['reference']['index'])
                prior=original
            if state['phase']=='retired':self.qualification(state)
        finally:self.state=previous
        return deepcopy(state)
    def original(self):
        value=dict(iosWorldWebActorRetirementOriginalVersion=1,owner=deepcopy(self.previous))
        self.validate_original(value);return value

    def validate_original(self,value):
        from adapters.original_file_reads import active,scope as read_scope
        from ios.adapters.emote_original_lease import EmoteOriginalLease
        with self.observer.validation_round():
            self.current_originals()
            context=_ORIGINALS.get();cache=None if context is None else context['originals'];memo=cache is not None
            # The readonly Source round has decoded the complete actual graph
            # and guards its original byte/inode inventory. Its exact durable
            # header and state bind those validated frame references; hashing
            # the expanded private DTOs again supplies no new original read.
            # New acquisitions, parser, owner, census or lease cannot inherit
            # an earlier result. Public data still receives separate copies.
            boundary=digest([value,self.state,self.previous,self.observer.state,self.observer.previous,
                self.observer.round_header(),self.source._round[:2],self.peer._round[:2],
                self.source.historical,self.peer.historical,
                None if self.observer.lease is None else [self.observer.lease.packet(),self.observer.lease.scope.previous]])
            methods=(self._validate_original,self.decode,self._decode,self.qualification,self._historical_frames,
                self._measure,self.native_frames,self.observer.derive,self.observer._derive,self.observer.validate_original,
                self.observer.entries,self.observer._entries)
            for owner in (self.source,self.peer):methods+=(owner._decode,owner._decode_frames,owner.validate_frame,owner.frame,owner.parts.verify_frame)
            key=boundary,tuple(getattr(method,'__func__',method) for method in methods)
            def guarded(pins):
                for path,signature in pins.items():need(EmoteOriginalLease.signature(path.lstat())==signature)
                self.current_originals()
            if memo and key in cache and cache[key][2].matches():
                result,pins,_membership=cache[key];guarded(pins);result=deepcopy(result);guarded(pins);return result
            if memo:
                # Isolate the complete decoder's actual operands. The outer
                # cleanup census also read mutable Feature/publisher heads;
                # their later normal CAS is not an immutable proof mutation.
                with read_scope(fresh=True) as reads:result=self._validate_original(value)
                paths=reads|{self.store.path,self.observer.store.path,self.source.store.path,self.peer.store.path}
                pins={path:EmoteOriginalLease.signature(path.lstat()) for path in paths}
                guarded(pins)
                # Propagate only reads actually performed by the successful
                # child decoder. A cache hit never invents new membership.
                if active():
                    with read_scope() as parent_reads:parent_reads.update(reads)
                # A new census cannot adopt replaced immutable operands by
                # silently refreshing this same exact original's old pins.
                if key in cache:guarded(cache[key][1])
                need(key in cache or len(cache)<64);cache[key]=(deepcopy(result),pins,OriginalMembership())
            else:result=self._validate_original(value)
            self.current_originals();return deepcopy(result)

    def current_originals(self):
        # These current checks are intentionally outside the deterministic
        # historical decoder memo. The Publisher separately retains its exact
        # original acquisition clock and final before-POST expiry checks.
        historical=self.source.historical
        need(type(historical) is bool and self.peer.historical is historical
            and all(owner.historical is (owner.readers is None) for owner in (self.source,self.peer)))
        if historical:
            self.source.guard_originals();self.peer.guard_originals()
        else:
            self.source.bound();self.peer.bound();need(self.observer.guard() is not False)
        need(same(self.store.read(),self.previous)
            and (self.previous is None or same(unpack(self.previous['payload']),[self.state])));self.observer.round_guard()

    def _validate_original(self,value):
        exact(value,{'iosWorldWebActorRetirementOriginalVersion','owner'});need(type(value['iosWorldWebActorRetirementOriginalVersion']) is int and value['iosWorldWebActorRetirementOriginalVersion']==1)
        state=self.decode(value['owner']);measured=self.qualification(state);sha=digest(value)
        return dict(ticket=measured['ticket'],scene=scene(measured['public']),acquisition=measured['acquisition'],retirement=dict(originalSha256=sha,quiet=measured['quiet'],
            provenance=dict(version=1,namespace='ios-world-web-actor-retirement',reference=dict(index=state['records'][-1]['reference']['index'],sha256=sha),originalSha256=sha)))
