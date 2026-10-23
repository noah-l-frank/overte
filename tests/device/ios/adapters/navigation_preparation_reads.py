"""Read actual interrupted preparation prefixes without promoting an outcome.

Partial host PNGs stay partial. Native command/storage journals retain every
original receipt and clock, including unknown delivery. No query is issued.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.native_vulkan_world_frame import PNG_LIMIT
from adapters.script_feature.history import same
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.navigation_whole_preparation import NavigationWholePreparation

VERSION=1


def frame_prefix(owner):
    owner._load();state=owner.state;path=owner.root/owner.name
    if state is None:need(not os.path.lexists(path));return None
    need(state['phase']!='removed')
    if state['file'] is None:need(not os.path.lexists(path));file=None
    else:
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            owner._file(stream.fileno());before=os.fstat(stream.fileno());raw=stream.read(PNG_LIMIT+1)
            owner._file(stream.fileno());after=os.fstat(stream.fileno())
        need(EmoteOriginalLease.signature(before)==EmoteOriginalLease.signature(after) and len(raw)==before.st_size)
        file=dict(device=before.st_dev,inode=before.st_ino,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    # A completed capture has its existing full original pixel/chunk decoder.
    # Released unknown/partial captures deliberately retain only their prefix.
    if state['phase']=='captured':owner.archive()
    need(same(owner.store.read(),state))
    return dict(originalSha256=digest(state),phase=state['phase'],file=file)


def inspect(preparation):
    need(type(preparation) is NavigationWholePreparation);f=preparation.flow;f.lock.assert_held()
    preparation.load();need(preparation.state is not None and preparation.state['phase']=='preparing' and f.store.read() is None)
    before=preparation.previous
    leases=[EmoteOriginalLease(root,[]) for root in {f.root,f.store.path.parent}];baselines={}
    for role,row in preparation.state['baselines'].items():
        owner=preparation.baseline(role,historical=True);frame=owner.owner();prefix=frame_prefix(frame)
        if owner.state is None:
            need(row['phase'] in ('planned','issued') and prefix is None)
            stem='navigation-baseline-'+f.run+'-'+role+'-'+row['requestId'][4:]+'-'
            need(all(not path.name.startswith(stem) for path in f.root.iterdir()))
            original=None;components={}
        else:
            need(row['phase']!='planned');original=digest(owner.previous);components=owner.originals()
            if row['phase']=='observed':need(row['ownerSha256']==original and owner.state['phase']=='observed')
            if owner.state['phase']=='observed':owner.archive()
            need(same(owner.store.read(),owner.previous))
        baselines[role]=dict(requestId=row['requestId'],originalSha256=original,
            componentsSha256=digest(components),frame=prefix)
    admission=preparation.admission(historical=True);row=preparation.state['admission']
    if admission.state is None:need(row['phase'] in ('planned','issued'));original=None
    else:
        need(row['phase']!='planned');original=digest(admission.previous)
        if row['phase']=='observed':need(original==row['ownerSha256'] and admission.state['phase']=='admitted')
        if admission.state['phase']=='admitted':admission.archive()
        need(same(admission.store.read(),admission.previous))
    for lease in leases:lease.guard()
    need(same(preparation.store.read(),before) and f.store.read() is None)
    return dict(iosNavigationPreparationReadsVersion=VERSION,runId=f.run,binding=preparation.state['binding'],
        status='failed-preparation-originals',preparationSha256=digest(before),baselines=baselines,admissionSha256=original)
