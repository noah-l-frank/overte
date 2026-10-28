"""Immutable callback owner drain originals inside existing Observer pending.

These are evidence carriers, never a second owner journal or current ACK.
Samples3 originals remain immutable as-of their original pending callback cut.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import os,stat
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.native_vulkan_world_frame import absent
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.original_frame_store import OriginalFrameStore,MAX_FRAMES
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import unpack,same
from ios.adapters.emote_callback_samples import IOSEmoteCallbackSamples,archived_sample
from ios.adapters.emote_callback_observation import validate_abandonment3
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from ios.adapters.emote_original_lease import EmoteOriginalLease

VERSION=4
NAMESPACE='emote-callback-drain'
PREFIX='iosEmoteCallbackDrain'


def store(root,binding,run,role,lock,*,guard=None,intent=None,monotonic=None):
    def guarded():lock.assert_held();return True
    def refused(*args):need(False)
    kwargs={} if monotonic is None else dict(monotonic=monotonic)
    return OriginalFrameStore(root,binding,run,role,guard or guarded,intent or refused,
        namespace=NAMESPACE,schema_prefix=PREFIX,**kwargs)


def sample_owner(value,sample,root,binding,run,role,lock):
    """Literal current owner snapshot, with immutable capture/prefix preserved."""
    need(type(value) is dict and sample['runId']==run and sample['role']==role and same(sample['binding'],binding))
    originals=unpack(sample['owner']);need(len(originals)==1 and type(originals[0]) is dict)
    prior=originals[0];need(value['phase']=='released' and absent(value['absence']))
    need(same({k:v for k,v in value.items() if k not in ('phase','absence','transcript')},
        {k:v for k,v in prior.items() if k not in ('phase','absence','transcript')}))
    old=unpack(prior['transcript']);new=unpack(value['transcript'])
    need(len(new)>=len(old) and same(new[:len(old)],old))
    class Frozen(PrivateFeatureState):
        def read(self):return deepcopy(value)
        def write(self,*args):need(False)
        def discard(self,*args):need(False)
    path=lock.path.with_name('graphics-world-frame-'+role+'-0-'+sample['requestId'][4:]+'.json')
    owner=VulkanWorldFrameOwner(Frozen(path),root,binding,run,role,0,sample['requestId'],lambda *_:need(False),lambda:True,source_lock=lock)
    owner._load();need(owner.state['phase']=='released' and absent(owner.state['absence']))
    if sample['phase']=='abandoned':
        validate_abandonment3(sample,root=root,binding=binding,run=run,role=role,lock=lock)
    else:
        # The same actual PNG/chunk/file inode must validate against the new
        # released owner and the old Sample3 snapshot independently.
        raw=owner.archive();need(raw is not None)
    return deepcopy(owner.state['absence'])


def sample_shell(value,root,binding,run,role,lock,policy):
    obj=object.__new__(IOSEmoteCallbackSamples)
    obj.root,obj.binding,obj.run,obj.role=Path(root),deepcopy(binding),run,role
    obj.lock,obj.policy=lock,deepcopy(policy)
    state=obj.decode(value);need(state['phase']=='ready' and state['rows'])
    expected={obj.sample_store(row).path for row in state['rows']}
    need(set(obj.root.glob('emote-sample-'+run+'-'+role+'-*.json'))==expected)
    return obj,state


def read_frame(originals,reference):return originals.read(originals.expand(reference))


def _prefix(originals,references,*,pending=None,membership=True):
    need(type(references) is list and len(references)<=MAX_FRAMES)
    expected=set();frames=[]
    for index,ref in enumerate(references,1):
        need(ref['index']==index);expanded=originals.expand(ref);expected.add(originals.path(expanded));frames.append(originals.read(expanded))
    if pending is not None:
        originals.original(pending);need(pending['index']==len(references)+1)
        path=originals.path(pending)
        if pending['phase']=='planned':need(not path.exists() and not path.is_symlink())
        elif pending['phase']=='saved':originals.read(pending);expected.add(path)
        else:
            import os,stat
            value=path.lstat();need(stat.S_ISREG(value.st_mode) and value.st_nlink==1 and value.st_uid==os.geteuid()
                and stat.S_IMODE(value.st_mode)==0o600 and value.st_size<=pending['bytes']
                and (value.st_dev,value.st_ino)==(pending['file']['device'],pending['file']['inode']));expected.add(path)
    if membership:
        actual={path for path in originals.root.iterdir() if path.name.startswith(NAMESPACE+'-')}
        need(actual==expected)
    return frames


def checked_read(roots,read):
    selected=[]
    for root in sorted(set(Path(root) for root in roots),key=lambda path:(len(path.parts),str(path))):
        if not any(root.is_relative_to(parent) for parent in selected):selected.append(root)
    leases=[EmoteOriginalLease(root,[]) for root in selected];failure=None
    try:return read()
    except BaseException as error:failure=error;raise
    finally:
        try:
            for lease in leases:lease.guard()
        except BaseException:
            if failure is None:raise
            failure.add_note('Callback original inventory exit also failed; original error preserved.')


def prefix(originals,references,*,pending=None,membership=True):
    return checked_read([originals.root],lambda:_prefix(originals,references,pending=pending,membership=membership))


def projection(value,*,root,binding,run,role,lock,policy,native_before=None,acquisition=None):
    return checked_read([root,lock.path.parent],lambda:_projection(value,root=root,binding=binding,run=run,role=role,
        lock=lock,policy=policy,native_before=native_before,acquisition=acquisition))


def _projection(value,*,root,binding,run,role,lock,policy,native_before=None,acquisition=None):
    """Pure typed re-read; current absence is never inferred from metadata pins."""
    exact(value,{'iosEmoteCallbackSampleOwnersVersion','samples','scope','drains','current'})
    need(type(value['iosEmoteCallbackSampleOwnersVersion']) is int and value['iosEmoteCallbackSampleOwnersVersion']==VERSION)
    originals=store(root,binding,run,role,lock);frames=prefix(originals,value['drains'],membership=False)
    samples,state=sample_shell(value['samples'],root,binding,run,role,lock,policy)
    scope_frame=read_frame(originals,value['scope']);exact(scope_frame,{'kind','scope','drainSpan'})
    need(scope_frame['kind']=='scope' and value['scope'] in value['drains'])
    scope=IOSEmoteRootedMarkerScope.archive(scope_frame['scope'],root=root,binding=binding,run=run,role=role,lock=lock)
    need(scope.state['phase']=='released' and scope.state['pending'] is None and scope.state['admission'] is not None
        and scope.state['fileOwnership'] is not None and scope.state['admission']['marker'] is not None)
    marker=scope.state['admission']['marker'];nonce=scope.state['fileOwnership']['nonce']
    span=scope_frame['drainSpan'];exact(span,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic','heads'})
    joined=PhaseWitnessPublisher.acquisition({key:span[key] for key in span if key!='heads'})
    quiet=scope.frames[scope.state['quiet'][-1]-1]['clockJoin']
    need(joined['hostBeforeEpochMs']>=quiet['hostAfterEpochMs'] and joined['hostBeforeMonotonic']>=quiet['hostAfterMonotonic']
        and type(span['heads']) is list and len(span['heads'])==len(state['rows']))
    if acquisition is not None:
        after=PhaseWitnessPublisher.acquisition(acquisition)
        need(joined['hostAfterEpochMs']<=after['hostBeforeEpochMs'] and joined['hostAfterMonotonic']<=after['hostBeforeMonotonic']
            and after['hostAfterEpochMs']-joined['hostBeforeEpochMs']<1500 and after['hostAfterMonotonic']-joined['hostBeforeMonotonic']<1.5)
    # Decode every retained carrier, not only the latest current cut. There is
    # no unowned/orphan prefix and no metadata-pin-as-read membership shortcut.
    for frame in frames:
        if frame.get('kind')=='scope':
            exact(frame,{'kind','scope','drainSpan'})
            old=IOSEmoteRootedMarkerScope.archive(frame['scope'],root=root,binding=binding,run=run,role=role,lock=lock)
            need(old.state['phase']=='released')
        else:
            exact(frame,{'kind','row','owner'});need(frame['kind']=='owner' and frame['row'] in state['rows'])
            sample=samples.record(frame['row']);sample_owner(frame['owner'],sample,root,binding,run,role,lock)
    need(type(value['current']) is list and len(value['current'])==len(state['rows']) and len({ref['index'] for ref in value['current']})==len(value['current']))
    for row,ref,head in zip(state['rows'],value['current'],span['heads']):
        need(ref in value['drains'] and ref['index']>value['scope']['index']);frame=read_frame(originals,ref)
        need(frame['kind']=='owner' and same(frame['row'],row));sample=samples.record(row)
        absence=sample_owner(frame['owner'],sample,root,binding,run,role,lock)
        events=unpack(frame['owner']['transcript']);last=events[-1]
        exact(head,{'requestId','commandId','receiptSha256'})
        need(head['requestId']==row['requestId'] and last['command']['operation'] in ('release','inspect')
            and head['commandId']==last['command']['commandId'] and head['receiptSha256']==digest(absence))
        old_sample=unpack(sample['owner'])[0];old_events=unpack(old_sample['transcript'])
        need(len(events)>len(old_events))
        for prior in frames[:value['scope']['index']-1]:
            if prior['kind']=='owner' and prior['row']['requestId']==row['requestId']:
                earlier=unpack(prior['owner']['transcript']);need(len(events)>len(earlier) and same(events[:len(earlier)],earlier))
        if sample['phase']!='abandoned':archived_sample(sample,root=root,binding=binding,run=run,role=role,lock=lock,policy=policy,
            marker_nonce=nonce,marker_url=marker['sourceUrl'])
        quiet=scope.frames[scope.state['quiet'][-1]-1]['clockJoin']['nativeAfter']
        need(absence['processId']==quiet['processId']==int(binding['processIdentity'])
            and absence['requestedEpochMs']>=quiet['capturedEpochMs'])
        if native_before is not None:
            need(absence['processId']==native_before['processId']
                and absence['capturedEpochMs']<=native_before['capturedEpochMs'])
    return scope


def history(observer):
    candidates=[]
    for ref in observer.state['records']:
        original=observer.original(ref)
        if original['iosEmoteObservationOriginalVersion']==4:candidates.append(original['sampleOwners']['drains'])
    pending=[row['pending'] for row in observer.state['abandoned']]
    if observer.state['pending'] is not None:pending.append(observer.state['pending'])
    for row in pending:
        extra=row['callbackDrains']
        if extra is not None:
            need(extra['original'] is None)
            candidates.append(extra['references'])
    result=[]
    for rows in candidates:
        need(type(rows) is list)
        if len(rows)>len(result):need(rows[:len(result)]==result);result=deepcopy(rows)
        else:need(rows==result[:len(rows)])
    originals=store(observer.root,observer.binding,observer.run,observer.role,observer.lock)
    prefix(originals,result);return result


def owner_signature(path):
    value=path.lstat()
    need(stat.S_ISREG(value.st_mode) and value.st_nlink==1 and value.st_uid==os.geteuid() and stat.S_IMODE(value.st_mode)==0o600)
    return (value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns)


def prepare(observer):
    """Persist real immutable originals through existing pending before facts."""
    pending=observer.state['pending'];need(pending is not None and pending['original'] is None and pending['sample'] is None)
    need(observer.samples.scope.state['phase']=='released')
    observer.samples.bound();previous=history(observer);samples=observer.samples.store.read()
    need(same(samples,observer.samples.previous) and same(samples,observer.samples.envelope(observer.samples.state)))
    _,state=sample_shell(samples,observer.root,observer.binding,observer.run,observer.role,observer.lock,observer.policy)
    need(len(previous)+1+len(state['rows'])<=MAX_FRAMES)
    extra=pending['callbackDrains'];need(extra is None)
    extra=dict(references=deepcopy(previous),original=None);pending['callbackDrains']=extra;observer.save()
    def intent(kind,value):
        need(kind=='original' and observer.state['pending'] is pending and pending['callbackDrains'] is extra)
        originals.original(value);need(value['index']==len(extra['references'])+1)
        old=extra['original']
        need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[k],old[k]) for k in value if k not in ('phase','file'))
            and (old['file'] is None or same(value['file'],old['file'])))
        extra['original']=deepcopy(value);observer.save()
    originals=store(observer.root,observer.binding,observer.run,observer.role,observer.lock,
        guard=observer.bound,intent=intent,monotonic=observer.monotonic)
    def append(value):
        ref=originals.write(len(extra['references'])+1,value)
        need(extra['original'] is not None and extra['original']['phase']=='saved')
        extra['references'].append(ref);extra['original']=None;observer.save();return ref
    need(observer._callback_drain_span is not None)
    scope=append(dict(kind='scope',scope=observer.samples.scope.snapshot(),drainSpan=deepcopy(observer._callback_drain_span)));current=[]
    for row in state['rows']:
        owner=observer.samples.owner(row);identity=owner_signature(owner.store.path);value=owner.store.read()
        need(owner_signature(owner.store.path)==identity);sample=observer.samples.record(row)
        sample_owner(value,sample,observer.root,observer.binding,observer.run,observer.role,observer.lock)
        current.append(append(dict(kind='owner',row=deepcopy(row),owner=value)))
        need(owner_signature(owner.store.path)==identity and same(owner.store.read(),value) and owner_signature(owner.store.path)==identity)
    observer.samples.bound();need(same(observer.samples.store.read(),samples))
    prefix(originals,extra['references'])
    return dict(iosEmoteCallbackSampleOwnersVersion=VERSION,samples=samples,scope=scope,drains=deepcopy(extra['references']),current=current)


def validate_pending(observer,pending):
    extra=pending['callbackDrains']
    if extra is None:return
    exact(extra,{'references','original'})
    originals=store(observer.root,observer.binding,observer.run,observer.role,observer.lock)
    prefix(originals,extra['references'],pending=extra['original'],membership=False)
