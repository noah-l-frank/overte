"""Typed once-publication metadata transitions around immutable native proof.

The readonly Source/Scope round ends before the real POST. Its fully validated
file inventories and exact headers still guard the final HTTP opener. Only the
actual publisher's two CAS write methods may authorize their new inode births.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager,ExitStack
from adapters.native_feature_observation import need
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from adapters.script_feature.history import same
from adapters.operation_transport_guard import scope as transport_scope
from feature_journeys.retirement_receipts import WEB_SCENE_STAGE
from ios.adapters.emote_original_lease import EmoteOriginalLease


class WorldWebPublicationRound:
    def __init__(self,retirement,publisher):
        from ios.adapters.world_web_actor_retirement import WorldWebActorRetirement
        from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
        kind=type(retirement)
        need(kind in (WorldWebActorRetirement,WorldWebSetupRetirement) and retirement.role=='actor' and type(publisher) is PhaseRetirementPublisher)
        self.retirement,self.publisher,self.observer=retirement,publisher,retirement.observer
        need(publisher.validate_original.__self__ is retirement and publisher.validate_original.__func__ is kind.validate_original
            and publisher.binding==retirement.binding and publisher.run==retirement.run and publisher.area=='world-web'
            and publisher.stage==WEB_SCENE_STAGE and publisher.lock is retirement.lock and publisher.live
            and publisher.store.path==retirement.peer.store.path.with_name('phase-retirement-world-web-'+retirement.run+'-actor.json'))
        need(publisher.save.__func__ is PhaseRetirementPublisher.save and publisher.store_record.__func__ is PhaseRetirementPublisher.store_record)
        publisher.bound();self.header=deepcopy(self.observer.round_header());self.previous=deepcopy(self.observer.previous)
        self.journal=publisher.store.path;self.record=publisher.record_store(len(publisher.state['records'])+1).path
        self.pins={self.journal:self.signature(self.journal),self.record:self.signature(self.record)}
        self.mutable=[self.journal,self.record];self.leases=[];self.issuing=False;self.close_readonly=None
        need(self.pins[self.record] is None)
    @staticmethod
    def signature(path):
        try:return EmoteOriginalLease.signature(path.lstat())
        except FileNotFoundError:return None
    def guard(self):
        observer,publisher=self.observer,self.publisher
        need(same(self.header,observer.round_header()) and same(self.previous,observer.previous)
            and same(observer.store.read(),observer.previous))
        observer.source.guard_originals();observer.peer.guard_originals()
        if observer.lease is not None:observer.lease.header()
        else:self.retirement.guard();self.retirement.scope.bound()
        for lease in self.leases:lease.guard()
        for path,pin in self.pins.items():need(self.signature(path)==pin)
        publisher.bound()
    def attach(self,leases):
        need(not self.leases);self.leases=leases;self.guard()

    @contextmanager
    def held(self):
        publisher=self.publisher;save,record,request=publisher.save,publisher.store_record,publisher.phase.client.request
        def saved():
            self.guard();result=save();self.pins[self.journal]=self.signature(self.journal);self.guard();return result
        def stored(row):
            self.guard();need(self.issuing and row['intent']['ordinal']==len(publisher.state['records'])+1)
            result=record(row);self.pins[self.record]=self.signature(self.record);self.guard();return result
        def requesting(path,*args,**kwargs):
            body=args[0] if args else kwargs.get('body')
            if path=='/runs/'+publisher.run+'/retirements' and body is not None:
                self.guard();need(not self.issuing and self.pins[self.record] is None)
                # Closing performs the complete original round's exit checks.
                # Final transport checks continue to guard those same files.
                self.close_readonly();self.guard();self.issuing=True
            return request(path,*args,**kwargs)
        publisher.save,publisher.store_record,publisher.phase.client.request=saved,stored,requesting
        try:
            with transport_scope(self.guard):
                with ExitStack() as readonly:
                    self.close_readonly=readonly.close
                    readonly.enter_context(self.observer.validation_round(publication=self))
                    yield
        finally:publisher.save,publisher.store_record,publisher.phase.client.request=save,record,request
