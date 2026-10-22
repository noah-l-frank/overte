"""Closed actor retirement receipts, separate from feature fact projections.

The actor's historical decoder establishes native cleanup. This journal owns
only immutable publication and binding; a hash or POST ACK proves no cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
from .contract import exact,identifier,number,result
from .scenarios import SCENARIOS

VERSION=2
READS=(1,2)
SCENE_STAGE="avatar-scene-retired"
SCENE_CLASSES=("entity", "file", "gpu", "marker-pixels", "qt-ui", "script-listener", "script-vm", "timer", "world-view")


def check(value):
    if not value:raise ValueError('Original phase retirement receipt is unavailable or invalid')


def sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def binding(value):
    exact(value,{'sourceRevision','artifactSha256','targetFingerprint','sessionSha256','generation','processIdentity'},'retirement binding')
    check(type(value['sourceRevision']) is str and re.fullmatch('[0-9a-f]{40}',value['sourceRevision'])
        and all(sha(value[key]) for key in ('artifactSha256','targetFingerprint','sessionSha256'))
        and type(value['generation']) is int and value['generation']>=0 and type(value['processIdentity']) is str
        and re.fullmatch('[1-9][0-9]{0,9}',value['processIdentity']))
    return value


def binding_from_context(value):
    # Actual SDK session identity stays private; the wire retains its exact
    # hash alongside the already qualified candidate/target/process binding.
    return binding(dict(**{key:value[key] for key in ('sourceRevision','artifactSha256','targetFingerprint','generation','processIdentity')},
        sessionSha256=hashlib.sha256(value['sessionId'].encode()).hexdigest()))


def acquisition(value):
    exact(value,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'},'retirement acquisition')
    a,b,c,d=[value[k] for k in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')]
    number(a,1);number(b,a,a+1500);number(c,0);number(d,c,c+1.5)
    check(b-a<1500 and d-c<1.5 and abs(b-a-(d-c)*1000)<=250);return value


def quiet(value,actor_binding):
    exact(value,{'hostAfterFirstEpochMs','hostBeforeLastEpochMs','hostAfterFirstMonotonic','hostBeforeLastMonotonic',
        'nativeAfterFirstEpochMs','nativeBeforeLastEpochMs','nativeAfterFirstMonotonicMs','nativeBeforeLastMonotonicMs',
        'nativeInstance','processId'},'retirement quiet originals')
    identifier(value['nativeInstance']);check(type(value['processId']) is int and str(value['processId'])==actor_binding['processIdentity'])
    intervals=[]
    for first,last,scale in (('hostAfterFirstEpochMs','hostBeforeLastEpochMs',1),('hostAfterFirstMonotonic','hostBeforeLastMonotonic',1000),
        ('nativeAfterFirstEpochMs','nativeBeforeLastEpochMs',1),('nativeAfterFirstMonotonicMs','nativeBeforeLastMonotonicMs',1)):
        a,b=number(value[first],0),number(value[last],0);check(3000<=(b-a)*scale<60000);intervals.append((b-a)*scale)
    check(max(intervals)-min(intervals)<=500);return value


def stage(value):
    return 'complete' if value.get('phaseRetirementVersion')==1 else value.get('stage')


def summary(value):
    return value['scene'] if stage(value)==SCENE_STAGE else value['cleanup']


def scene(value,run,sequence):
    exact(value,{'sceneRetirementVersion','runId','sequence','capturedEpochMs','retired','remaining','lifecycle'},'closed Avatar scene retirement summary')
    check(type(value['sceneRetirementVersion']) is int and value['sceneRetirementVersion']==1
        and value['runId']==run and type(value['sequence']) is int and value['sequence']==sequence
        and value['retired']==list(SCENE_CLASSES) and value['remaining']==['account-session'])
    lifecycle(value['lifecycle']);number(value['capturedEpochMs'],1)
    return value


def lifecycle(value):
    exact(value,{'backgrounds','activations','launches'},'retirement lifecycle')
    check(all(type(count) is int and 0<=count<=1000000 for count in value.values()) and value['launches']>=1)


def body(value,*,run=None,area=None,phase_instance=None):
    check(type(value) is dict and type(value.get('phaseRetirementVersion')) is int and value['phaseRetirementVersion'] in READS)
    version=value['phaseRetirementVersion'];kind=stage(value)
    check(kind in ('complete',SCENE_STAGE) and (kind!='avatar-scene-retired' or version==2 and value.get('area')=='avatar-people'))
    exact(value,{'phaseRetirementVersion','runId','area','phaseInstance','ticket','role','actorSequence','binding','originalSha256',
        'acquisition','quiet','provenance'}|({'stage'} if version==2 else set())|({'scene'} if kind==SCENE_STAGE else {'cleanup'}),'retirement publication')
    check(value['role']=='actor' and value['area'] in SCENARIOS
        and (area is None or value['area']==area) and (run is None or value['runId']==run)
        and (phase_instance is None or value['phaseInstance']==phase_instance))
    identifier(value['runId']);identifier(value['phaseInstance']);identifier(value['ticket']);binding(value['binding'])
    check(sha(value['originalSha256']) and type(value['actorSequence']) is int and value['actorSequence']>0)
    public=summary(value)
    if kind==SCENE_STAGE:scene(public,value['runId'],value['actorSequence'])
    else:
        exact(public,{'schemaVersion','contractVersion','runId','sequence','capturedEpochMs','resources','lifecycle'},'closed complete retirement summary')
        check(type(public['schemaVersion']) is int and public['schemaVersion']==1 and type(public['contractVersion']) is int and public['contractVersion']==16
            and type(public['sequence']) is int and public['sequence']>0 and type(public['resources']) is list and public['resources']==[])
        lifecycle(public['lifecycle']);number(public['capturedEpochMs'],1)
    clock=acquisition(value['acquisition'])
    check(public['runId']==value['runId'] and public['sequence']==value['actorSequence']
        and clock['hostBeforeEpochMs']<=public['capturedEpochMs']<=clock['hostAfterEpochMs'])
    quiet(value['quiet'],value['binding']);check(value['quiet']['hostBeforeLastEpochMs']<=clock['hostBeforeEpochMs']
        and value['quiet']['hostBeforeLastMonotonic']<=clock['hostBeforeMonotonic'])
    provenance=value['provenance'];exact(provenance,{'version','namespace','reference','originalSha256'},'retirement original provenance')
    check(type(provenance['version']) is int and provenance['version']==1 and type(provenance['namespace']) is str
        and re.fullmatch('[a-z][a-z0-9-]{0,63}',provenance['namespace']) and type(provenance['reference']) is dict
        and provenance['originalSha256']==value['originalSha256'])
    ref=provenance['reference'];exact(ref,{'index','sha256'},'retirement original reference')
    check(type(ref['index']) is int and 1<=ref['index']<=1000000000 and ref['sha256']==value['originalSha256']
        and len(json.dumps(value,allow_nan=False).encode())<=262144)
    return value


class PhaseRetirementJournal:
    def __init__(self,journal):self.journal=journal;self.runs={}

    def publish(self,run,value):
        with self.journal.lock:
            self.runs={key:rows for key,rows in self.runs.items() if key in self.journal.runs}
            current=self.journal.runs[identifier(run)];body(value,run=run,area=current['area'],phase_instance=self.journal.phase_instance)
            check(current['stimulus']==dict(verb='cleanup',inputs={}) and current['ticket']==value['ticket'])
            check(value['quiet']['hostAfterFirstEpochMs']>=current['activeEpochMs'])
            rows=self.runs.get(run,[]);check(len(rows)<128)
            if rows:check(value['actorSequence']>rows[-1]['actorSequence'] and value['binding']==rows[0]['binding'])
            same_ticket=[row for row in rows if row['ticket']==value['ticket']]
            check(stage(value)!=SCENE_STAGE or not same_ticket)
            captured=summary(value)['capturedEpochMs'];now=self.journal.clock()
            check(current['activeEpochMs']<=captured<=now+250 and now-captured<=1500)
            rows.append(dict(deepcopy(value),sequence=len(rows)+1,receivedEpochMs=now,receiptSha256=digest(value)))
            self.runs[run]=rows

    def snapshot(self,run):
        with self.journal.lock:
            current=self.journal.runs[identifier(run)]
            return dict(phaseRetirementJournalVersion=VERSION,runId=run,area=current['area'],phaseInstance=self.journal.phase_instance,
                ticket=current['ticket'],sampleEpochMs=self.journal.clock(),entries=deepcopy(self.runs.get(run,[])))
