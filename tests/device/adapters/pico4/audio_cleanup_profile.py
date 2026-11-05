"""Explicit Audio-only cleanup selection and prospective aggregate custody.

This profile grants no input, process replacement, resource absence or acoustic
verdict. The original raw archive remains the single global admission owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat

from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import context
from adapters.script_journey.history import canonical,MAX_RAW
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import identifier

VERSION=1
PART=65536
PROFILE_LIMIT=4096
FENCE_LIMIT=4096
PROCESS_OWNER_BYTES=32768
PROCESS_CAPTURE_BYTES=131072
# Full root/current/prepared copies plus one bounded literal/role work overlap.
PROSPECTIVE_BYTES=6*PART+262144


def profile(value):
    version=value.get('picoAudioCleanupProfileVersion') if type(value) is dict else None
    exact(value,{'picoAudioCleanupProfileVersion','runId','binding',
                 'hostProcessIdentity','startedMonotonic','deadlineMonotonic'}
                 |({'quietPollingProfile'} if version in (2,3) else set())
                 |({'cleanupWorkspacePolicy'} if version==3 else set()))
    need(type(version) is int and version in (VERSION,2,3))
    if version in (2,3):need(type(value['quietPollingProfile']) is str
        and value['quietPollingProfile']=='work-inclusive-450ms')
    if version==3:need(value['cleanupWorkspacePolicy']=='book-before-cleanup-constructor' and type(value['cleanupWorkspacePolicy']) is str)
    identifier(value['runId']);context(value['binding'])
    need(type(value['hostProcessIdentity']) is str and value['hostProcessIdentity']==host_identity()
         and number(value['startedMonotonic'],0,1e15)
         and number(value['deadlineMonotonic'],value['startedMonotonic'],1e15)
         and value['deadlineMonotonic']-value['startedMonotonic']==120)
    raw=canonical(value);need(len(raw)<=PROFILE_LIMIT);return raw


class AudioCleanupBudget1:
    """One cold-selected prospective charge, held through constructor failure.

    Physical originals stay in the existing fresh aggregate scan. This object
    contributes only its additional decoded/prospective overlap. It is not a
    new quota, an alias for retired sources or a cleanup permit.
    """
    def __init__(self,value,source_lock):
        need(type(source_lock) is ScriptSourceLock)
        raw=profile(value)
        self.lock=source_lock;self.raw=raw;self.value=deepcopy(value)
        self.sha=hashlib.sha256(raw).hexdigest();self.actor=None;self.recipe=None
        self.failed=False;self.closed=False
        self.factory_hold=self._original_factory_hold=None
        self.factory_failure=None
        self._original_lock=source_lock;self._original_raw=raw
        self._original_sha=self.sha
        self.workspace=self._workspace=(value['picoAudioCleanupProfileVersion']!=3,None)
        self.prospective=PROSPECTIVE_BYTES if self.workspace[0] else 0
        self.fixed=3*PROFILE_LIMIT+3*FENCE_LIMIT+PROCESS_OWNER_BYTES
        self.last_inventory=None
        self.row_slots=0;self.decode_hold=0
        self._cost_seal=(0,0)
        self.sampler=None
        self.new_samplers=self._original_new_samplers=()
        self.new_seals=self._original_new_seals=()
        self.new_metadata=self._original_new_metadata=0
        self.common_owner=self._original_common_owner=None
        self.common_authenticated=self._original_common_authenticated=False
        self.common_credit=self._original_common_credit=0
        self.quiet_credit=self._original_quiet_credit=0
        self.decode_seal=None
        self.decode_handback=self._original_decode_handback=False
        self.preserve_other_decode=self._original_preserve_other_decode=False
        self.decode_seal_metadata=self._original_decode_seal_metadata=0
        self.sampler_metadata=self._original_sampler_metadata=0
        self.process_source=None
        self.process_hold=self._original_process_hold=0
        self.old_frozen=self._original_old_frozen=False
        self.freeze_receipt=self._original_freeze_receipt=None

    def guard(self):
        need(not self.closed and self.lock is self._original_lock
             and type(self.raw) is bytes and self.raw is self._original_raw
             and self.sha==self._original_sha==hashlib.sha256(self.raw).hexdigest()
             and profile(self.value)==self.raw and self.fixed==3*PROFILE_LIMIT+3*FENCE_LIMIT+PROCESS_OWNER_BYTES
             and type(self.workspace) is tuple and self.workspace is self._workspace and len(self.workspace)==2
             and type(self.workspace[0]) is bool
             and (self.value['picoAudioCleanupProfileVersion']==3 or self.workspace==(True,None))
             and type(self.prospective) is int and self.prospective==(PROSPECTIVE_BYTES if self.workspace[0] else 0)
             and type(self.process_hold) is int and self.process_hold==self._original_process_hold
             and 0<=self.process_hold<=8*PROCESS_CAPTURE_BYTES and self.process_hold%PROCESS_CAPTURE_BYTES==0
             and self.new_samplers is self._original_new_samplers
             and type(self.new_samplers) is tuple and len(self.new_samplers) in (0,2)
             and self.new_seals is self._original_new_seals
             and type(self.new_seals) is tuple and len(self.new_seals) in (0,2)
             and type(self.new_metadata) is int and self.new_metadata==self._original_new_metadata
             and self.new_metadata in (0,2*(65536+262144))
             and type(self.common_authenticated) is bool and self.common_authenticated is self._original_common_authenticated
             and self.common_owner is self._original_common_owner
             and type(self.common_credit) is int and self.common_credit==self._original_common_credit
             and self.common_credit in (0,2*1048576)
             and type(self.quiet_credit) is int and self.quiet_credit==self._original_quiet_credit
             and self.quiet_credit in (0,3*1048576)
             and type(self.sampler_metadata) is int and self.sampler_metadata==self._original_sampler_metadata
             and self.sampler_metadata in (0,65536)
             and type(self.decode_handback) is bool and self.decode_handback is self._original_decode_handback
             and type(self.preserve_other_decode) is bool and self.preserve_other_decode is self._original_preserve_other_decode
             and self.decode_seal_metadata==self._original_decode_seal_metadata
             and type(self.decode_seal_metadata) is int and self.decode_seal_metadata in (0,262144)
             and self.factory_hold is self._original_factory_hold
             and (self.factory_hold is None or type(self.factory_hold) is tuple and len(self.factory_hold)==3
                  and self.factory_hold[1] is self.recipe and self.factory_hold[2] is self.actor)
             and type(self.failed) is bool
             and type(self.row_slots) is int and 0<=self.row_slots<=512
             and type(self.decode_hold) is int and 0<=self.decode_hold<=MAX_RAW
             and (self.row_slots,self.decode_hold)==self._cost_seal
             and type(self.old_frozen) is bool and self.old_frozen is self._original_old_frozen
             and self.freeze_receipt is self._original_freeze_receipt
             and ((not self.old_frozen and self.freeze_receipt is None)
                  or self.old_frozen and type(self.freeze_receipt) is bytes
                  and len(self.freeze_receipt)<=FENCE_LIMIT))

    def require_cleanup_workspace(self):
        self.guard();need(not self.failed and self.workspace[0] and self.prospective==PROSPECTIVE_BYTES)
        if self.value['picoAudioCleanupProfileVersion']==3:
            need(self.actor is not None and self.actor.raws.literal(self.workspace[1]) is None)

    def begin_cleanup(self):
        """Profile3 books the FULL serial cleanup workspace before any ctor IO."""
        self.guard();need(not self.failed and self.actor is not None)
        if self.workspace[0]:return
        need(self.value['picoAudioCleanupProfileVersion']==3 and self.recipe.state['cursor']==14
            and self.recipe.state['pending'] is None and self.actor.state['pending'] is None
            and self.process_source is self.sampler is self.common_owner is None
            and self.new_samplers==() and self.row_slots==self.decode_hold==0)
        try:
            with self.actor.raws.lock.held():
                # Existing bank enforces FULL old Root/current/pending and the
                # complete new cleanup domain before even a marker is written.
                token=self.actor.raws.reserve('audio-cleanup-workspace',dict(profileSha256=self.sha),1,
                    side_bytes=PROSPECTIVE_BYTES)
                reference=self.actor.raws.retain(token,None)
                # No constructor, SDK, callback or other thread can intervene
                # under this same bank lock. No actual workspace has been used.
                self.prospective=PROSPECTIVE_BYTES
                self.workspace=self._workspace=(True,reference)
                self.guard()
        except BaseException as error:
            self.failed=True
            if self.factory_failure is None:self.factory_failure=(error,error.__traceback__)
            raise

    def require_old_acquisition(self,actor):
        # Run before old observation CAS, SDK dispatch, or a PC operation.
        # Archival raw authority and resource-only billing remain available.
        self.guard()
        need(actor is self.actor and not self.failed and not self.old_frozen)

    def freeze_old_acquisition(self,owner):
        from adapters.pico4.audio_cleanup_owner import PicoAudioCleanupOwner1,reference
        self.guard()
        need(type(owner) is PicoAudioCleanupOwner1 and owner is getattr(self,'cleanup_owner',None)
             and owner.budget is self and owner.actor is self.actor
             and owner.recipe is self.recipe and not self.failed and not self.old_frozen)
        actor=self.actor;coordinator=owner.coordinator
        # Actual recorder retirement shuts the executor down first. No job may
        # race the selected irreversible admission fence.
        need(actor.executor is None and all(future.done() for future in actor.jobs.values()))
        with actor.held():
            actor.bound();coordinator.bound();self.recipe.load();self.recipe.resources()
            need(self.recipe.state['cursor']==14 and self.recipe.state['pending'] is None
                 and len(coordinator.state['completed'])==14 and coordinator.state['pending'] is None
                 and coordinator.state['digitalRetired'] is True
                 and actor.state['pending'] is actor.state['publication'] is None
                 and actor.state['quiet'] is not None and actor.state['quiet']['complete'] is True
                 and all(job['retired'] is True for job in actor.state['jobs']))
            receipt=canonical(dict(audioCleanupAcquisitionFenceVersion=1,
                actorHeader=actor.header_ref,actorRoot=actor.pin,
                coordinatorRoot=coordinator.pin,recipeRoot=reference(self.recipe.store)))
            need(len(receipt)<=FENCE_LIMIT)
            self.freeze_receipt=self._original_freeze_receipt=receipt
            self.old_frozen=self._original_old_frozen=True
            # Never thaw, including a later CAS/Stop/Launch/quiet failure.
            self.guard()
        return receipt

    def current_bytes(self,actor):
        self.guard();need(actor is self.actor)
        # This prospective slot is not released merely because a constructor or
        # source call returned. The later cleanup owner must take exact custody.
        return self.fixed+self.prospective+4096*self.row_slots+self.decode_hold+self.process_hold+self.sampler_metadata+self.decode_seal_metadata+self.new_metadata+self.quiet_credit+self.common_credit

    def inventory_before_allocation(self,path):
        """Stat the entire existing namespace before decoding any file bytes."""
        self.guard();path=Path(path)
        count=directories=0;total=0;stack=[path]
        while stack:
            directory=stack.pop();directories+=1
            need(directories<=64 and len(str(directory))<=1024)
            before=directory.lstat()
            need(stat.S_ISDIR(before.st_mode) and not stat.S_ISLNK(before.st_mode))
            with os.scandir(directory) as entries:
                for entry in entries:
                    item=Path(entry.path);info=entry.stat(follow_symlinks=False)
                    need(not stat.S_ISLNK(info.st_mode))
                    if stat.S_ISDIR(info.st_mode):
                        need(len(stack)<64 and len(str(item))<=1024)
                        stack.append(item)
                    else:
                        need(stat.S_ISREG(info.st_mode))
                        total+=info.st_size
                        need(total+self.fixed+self.prospective<=MAX_RAW)
                        count+=1
                        need(count<=4096)
            after=directory.lstat()
            need((before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)==
                 (after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns))
        # This is only a pre-constructor physical floor. It does not replace
        # the original complete raw/decoded/part bill at actual admission.
        self.last_inventory=(count,total)
        return total

    def admit_actor(self,actor,recipe):
        from adapters.pico4.audio_pc_actor import PicoAudioPCActor
        from adapters.pico4.audio_recipe import PicoAudioRecipe
        self.guard()
        need(type(actor) is PicoAudioPCActor and type(recipe) is PicoAudioRecipe
             and self.actor is None and not self.failed
             and recipe.lock is self.lock and recipe.run==self.value['runId']
             and recipe.binding==self.value['binding'])
        # Hold the actual partial actor BEFORE inventory/allocation can fail.
        self.actor=actor;self.recipe=recipe
        try:
            with self.lock.held():
                self.inventory_before_allocation(recipe.store.path.parent)
                need(recipe.state is None and recipe.disk is None)
        except BaseException:
            self.failed=True
            raise

    def create_old_sampler(self,io):
        from adapters.pico4.audio_cleanup_snapshot import AudioCleanupSnapshot1
        self.guard();need(io is getattr(self,'restart_io',None) and self.actor is not None
            and self.sampler is None and not self.failed and not self.old_frozen)
        sampler=object.__new__(AudioCleanupSnapshot1)
        self.sampler=sampler
        self.sampler_metadata=self._original_sampler_metadata=65536
        try:
            self.check_global(io)
            AudioCleanupSnapshot1.__init__(sampler,self,io)
        except BaseException:self.failed=True;raise
        return sampler

    def book_decode_seal(self,sampler,*,success_handback=False,preserve_other_decode=False):
        from adapters.pico4.audio_cleanup_decode import ClosedAudioReaderSeal
        self.guard();need(type(success_handback) is bool and type(preserve_other_decode) is bool
            and (not preserve_other_decode or success_handback)
            and sampler is self.sampler and sampler.budget is self
            and self.decode_seal is None and not self.failed and not sampler.reading
            and sampler.sequence==0 and not sampler.io.references and self.decode_hold==0)
        seal=object.__new__(ClosedAudioReaderSeal)
        self.decode_seal=seal
        self.decode_handback=self._original_decode_handback=success_handback
        self.preserve_other_decode=self._original_preserve_other_decode=preserve_other_decode
        self.decode_seal_metadata=self._original_decode_seal_metadata=262144
        try:
            self.check_global(sampler.io)
            ClosedAudioReaderSeal.__init__(seal,sampler)
            sampler.seal=seal
        except BaseException as error:
            sampler.failed=True;self.failed=True
            if sampler.failure is None:sampler.failure=(error,error.__traceback__)
            raise
        return seal

    def create_new_samplers(self,io):
        from adapters.pico4.audio_cleanup_owner import PicoAudioCleanupOwner1
        from adapters.pico4.audio_cleanup_snapshot import AudioCleanupSnapshot1
        from adapters.pico4.audio_cleanup_decode import ClosedAudioReaderSeal
        self.guard();owner=getattr(self,'cleanup_owner',None)
        need(type(owner) is PicoAudioCleanupOwner1 and owner.budget is self
            and io is getattr(self,'restart_io',None) and owner.io is io
            and self.old_frozen and not self.failed and self.preserve_other_decode
            and self.decode_handback and not self.new_samplers and not self.new_seals
            and self.new_metadata==0 and io.query is None and len(io.source_sets)==2)
        owner.guard();need(owner.state['phase']=='new-bound')
        # Both sampler+seal domains coexist with every old/proof/root charge.
        # Book before either fresh reader constructor or identity SDK operation.
        self.new_metadata=self._original_new_metadata=2*(65536+262144)
        self.new_samplers=self._original_new_samplers=tuple(
            object.__new__(AudioCleanupSnapshot1) for _ in range(2))
        try:
            self.check_global(io)
            for sampler,role in zip(self.new_samplers,('primary','actor')):
                AudioCleanupSnapshot1.__init__(sampler,self,io,epoch='new',role=role,
                    binding=owner.state['newBinding'])
            need(len(io.source_sets)==4)
            self.new_seals=self._original_new_seals=tuple(
                object.__new__(ClosedAudioReaderSeal) for _ in range(2))
            for sampler,seal in zip(self.new_samplers,self.new_seals):
                ClosedAudioReaderSeal.__init__(seal,sampler)
                sampler.seal=seal
            owner.guard();self.check_global(io)
            return self.new_samplers
        except BaseException as error:
            owner.poison(error)
            raise

    def admit_new_quiet(self,owner):
        from adapters.pico4.audio_cleanup_owner import PicoAudioCleanupOwner1
        self.guard();need(type(owner) is PicoAudioCleanupOwner1 and owner is getattr(self,'cleanup_owner',None)
            and owner.budget is self and not self.failed and self.old_frozen
            and owner.state['phase']=='new-bound' and self.quiet_credit==0
            and len(self.new_samplers)==len(self.new_seals)==2)
        # One full<=16KiB decode at64x, two compact<=4KiB projections at64x,
        # bounded41-row/token/clock metadata, framed literal/encoder overlap.
        # The complete permanent3MiB stays held through success or failure.
        self.quiet_credit=self._original_quiet_credit=3*1048576
        self.check_global(owner.io)

    def create_common_cleanup(self,*,authenticated_actor=False):
        from adapters.pico4.audio_cleanup_common import AudioCommonCleanup1
        owner=getattr(self,'cleanup_owner',None)
        self.guard();need(type(authenticated_actor) is bool and not self.failed
            and self.common_owner is None and self.common_credit==0
            and owner is not None and type(owner.state) is dict
            and owner.state['phase']=='new-bound' and self.quiet_credit==0)
        self.common_authenticated=self._original_common_authenticated=authenticated_actor
        self.common_credit=self._original_common_credit=2*1048576
        self.check_global(owner.io)
        participant=object.__new__(AudioCommonCleanup1);self.common_owner=self._original_common_owner=participant
        try:AudioCommonCleanup1.__init__(participant,owner)
        except BaseException as error:owner.poison(error);raise
        return participant

    def create_process_source(self):
        from adapters.pico4.audio_cleanup_process import AudioCleanupProcessOriginals
        self.guard();need(self.actor is not None and self.process_source is None and not self.failed)
        owner=object.__new__(AudioCleanupProcessOriginals)
        self.process_source=owner  # Strong before constructor, file or SDK work.
        try:AudioCleanupProcessOriginals.__init__(owner,self)
        except BaseException:self.failed=True;raise
        return owner

    def admit_process_capture(self,source):
        self.guard();need(source is self.process_source and not self.failed
            and self.process_hold<8*PROCESS_CAPTURE_BYTES)
        self.process_hold+=PROCESS_CAPTURE_BYTES
        self._original_process_hold=self.process_hold
        self.check_global(source)

    def charge_row(self,io,*,reserve_follows=False):
        self.guard();need(type(reserve_follows) is bool
            and io is getattr(self,'restart_io',None) and not self.failed and self.row_slots<512)
        self.row_slots+=1;self._cost_seal=(self.row_slots,self.decode_hold)
        # Only the two closed IO callsites opt in: the immediate next call is
        # the SAME RawArchive.reserve, before any SDK/send/getter or parser.
        # It freshly verifies this exact bank and current other_bill, including
        # our newly booked row, then checks the STRICTER new-literal/part/
        # pending/side/3*PART totals before any clock or other callback.
        # Direct/default row booking retains its original full global check.
        if not reserve_follows:self.check_global(io)

    def check_global(self,io):
        self.guard();need(self.actor is not None and (io is getattr(self,'restart_io',None)
            or self.process_source is not None and io is self.process_source))
        bank=self.actor.raws
        try:
            with bank.lock.held():
                bank.verify();other=bank.other_bill();ours=bank.bill()
                pending=bank.state['pending']
                overlap=sum(row['limit']+row['sideBytes'] for row in pending)
                need(other['parts']+ours['parts']+sum(row['parts'] for row in pending)<=512
                     and other['storedBytes']+ours['storedBytes']+overlap+3*PART<=MAX_RAW
                     and other['decodedBytes']+ours['decodedBytes']+overlap+3*PART<=MAX_RAW)
        except BaseException:
            self.failed=True
            raise

    def hold_decode(self,io,raw):
        self.guard();need(io is getattr(self,'restart_io',None) and type(raw) is str)
        # DRAFT conservative scratch only; no successful release/MAX discount is
        # implemented. Keep all decoder charges strongly through failure/exit.
        cost=64*len(raw)+3*PART
        need(cost<=MAX_RAW-self.decode_hold)
        self.decode_hold+=cost;self._cost_seal=(self.row_slots,self.decode_hold)
        self.check_global(io)
