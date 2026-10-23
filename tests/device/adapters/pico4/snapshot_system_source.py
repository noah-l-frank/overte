"""Passive original OS scope; no chooser input or foreground-only Qt access.

Choreography reviewed from frozen Phone b62e012f1328e30b80604bb447a60db0d8a748df:
prepare in original foreground, retain the exact source-lock acquisition across
an owner-authorized handoff, requalify actual candidate/kernel/session and OS
identity. Phone touch, receiver authority and actor facade are not reused.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import context
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey.history import canonical
from feature_journeys.contract import typed_equal

PRIMARY='org.overte.pico'
RESOLVE=('cmd','package','resolve-activity','--brief','--user','0','-a','android.intent.action.CHOOSER')
PACKAGE=re.compile(r'(?:android|[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+)')
ACTIVITY=re.compile(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_$]+)+')


def component(value):
    need(type(value) is str and value.count('/')==1)
    package,activity=value.split('/');need(PACKAGE.fullmatch(package) is not None)
    if activity.startswith('.'):activity=package+activity
    need(ACTIVITY.fullmatch(activity) is not None);return package+'/'+activity


def resolved(raw):
    need(type(raw) is str and 0<len(raw.encode())<=4096)
    rows=raw.strip().splitlines();need(1<=len(rows)<=2)
    if len(rows)==2:need(re.fullmatch(r'priority=-?[0-9]+ preferredOrder=-?[0-9]+ match=0x[0-9a-fA-F]+ specificIndex=-?[0-9]+ isDefault=(true|false)',rows[0]) is not None)
    actual=component(rows[-1]);need(actual.split('/')[0] not in (PRIMARY,'org.overte.e2e.snapshotreceiver'));return actual


def current(raw):
    need(type(raw) is str and 0<len(raw.encode())<=262144)
    pattern=re.compile(r'^\s*(?:mResumedActivity|topResumedActivity|ResumedActivity|Resumed):.*?\s([A-Za-z0-9._]+/[A-Za-z0-9._$]+)')
    values={component(match[1]) for line in raw.splitlines() if (match:=pattern.search(line))}
    need(len(values)==1);return values.pop()


def uid(raw,package):
    need(type(raw) is str and 0<len(raw.encode())<=16384 and PACKAGE.fullmatch(package) is not None)
    found=[]
    for line in raw.strip().splitlines():
        row=re.fullmatch(r'package:([A-Za-z][A-Za-z0-9_.]+) uid:([1-9][0-9]{0,9})',line);need(row is not None)
        if row[1]==package:found.append(int(row[2]))
    need(len(found)==1);return found[0]


class PicoSnapshotSystemSource:
    """One continuous original lock acquisition, a read-only OS query surface.

    authority is the parent's exact durable handoff/phase/graph requalification;
    it must fail before any SDK read when that original owner is unavailable.
    This source cannot admit receiver UI: no Pico-qualified receiver APK exists.
    """
    def __init__(self,binding,lock,status,shell,clock_ms,authority,*,monotonic=time.monotonic):
        context(binding);need(isinstance(lock,ScriptSourceLock) and all(callable(fn) for fn in (status,shell,clock_ms,authority,monotonic)))
        lock.assert_held();self.acquisition=lock._owner
        self.binding,self.lock=deepcopy(binding),lock
        self.status,self.shell,self.clock_ms,self.authority,self.monotonic=status,shell,clock_ms,authority,monotonic
        self.chooser=self.last=None;self.last_host=None;self._chooser_admission=None;self._chooser_sha=None

    def authority_only(self):
        self.lock.assert_held();need(self.lock._owner is self.acquisition and self.authority() is True)
        if self._chooser_admission is None:need(self.chooser is None and self._chooser_sha is None)
        else:
            need(self.chooser is not None and hashlib.sha256(canonical(self.chooser)).hexdigest()==self._chooser_sha
                and typed_equal(self.chooser,decode(self._chooser_admission.decode('utf-8'))))

    def guard(self):
        self.authority_only()
        value=self.status();exact(value,{'binding','foreground','running'})
        need(typed_equal(value['binding'],self.binding) and value['running'] is True and type(value['foreground']) is bool)
        self.authority_only();return value

    def begin(self):
        start=self.monotonic();need(number(start,0,1e15) and (self.last_host is None or start>=self.last_host))
        before=self.guard();requested=self.clock_ms();need(integer(requested,1));return start,requested,before

    def finish(self,start,requested,before,active,owner=None,chooser=None):
        after=self.guard();need(typed_equal(after,before))
        # Exact Activity/UID is read after the last candidate/session guard.
        # That guard must not advance to a foreign window under the same package.
        final_raw=self.shell('dumpsys','activity','activities');need(current(final_raw)==active)
        final_source=dict(activityRaw=final_raw,resolutionRaw='',chooserUidRaw='',activeUidRaw='')
        if chooser is not None:
            actual,expected_uid=chooser;package=actual.split('/')[0]
            final_source['resolutionRaw']=self.shell(*RESOLVE)
            final_source['chooserUidRaw']=self.shell('cmd','package','list','packages','-U','--user','0',package)
            need(resolved(final_source['resolutionRaw'])==actual and uid(final_source['chooserUidRaw'],package)==expected_uid)
        if owner is not None:
            final_source['activeUidRaw']=self.shell('cmd','package','list','packages','-U','--user','0',active.split('/')[0])
            need(uid(final_source['activeUidRaw'],active.split('/')[0])==owner)
        final_copy=deepcopy(final_source)
        completed=self.seal(start,requested)
        return completed,final_source,final_copy

    def seal(self,start,requested):
        # Parent graph/phase and lock only: never refresh a native/SDK source in
        # this last authority check or turn it into an unbounded refresh loop.
        self.authority_only();completed=self.clock_ms();now=self.monotonic()
        need(integer(completed,requested) and completed-requested<=1500 and number(now,start,1e15) and now-start<=1.5)
        self.last_host=now;return completed

    def prepare(self):
        need(self.chooser is None);start,requested,before=self.begin();need(before['foreground'])
        active_raw=self.shell('dumpsys','activity','activities');active=current(active_raw);need(active.split('/')[0]==PRIMARY)
        raw=self.shell(*RESOLVE);actual=resolved(raw);package=actual.split('/')[0]
        uid_raw=self.shell('cmd','package','list','packages','-U','--user','0',package);owner=uid(uid_raw,package)
        need(resolved(self.shell(*RESOLVE))==actual and current(self.shell('dumpsys','activity','activities'))==active)
        value=dict(component=actual,uid=owner,resolutionRaw=raw,uidRaw=uid_raw,requestedEpochMs=requested,capturedEpochMs=0)
        saved=deepcopy(value);result=deepcopy(value)
        captured,final,final_copy=self.finish(start,requested,before,active,chooser=(actual,owner))
        saved['finalSource']=final;result['finalSource']=final_copy
        saved['capturedEpochMs']=result['capturedEpochMs']=captured
        admission=canonical(saved);need(typed_equal(saved,decode(admission.decode('utf-8'))))
        digest=hashlib.sha256(admission).hexdigest();self.seal(start,requested)
        self.chooser=saved;self._chooser_admission=admission;self._chooser_sha=digest;return result

    def capture(self):
        need(self.chooser is not None);start,requested,before=self.begin()
        raw=self.shell('dumpsys','activity','activities');active=current(raw);package=active.split('/')[0]
        if package==PRIMARY:need(before['foreground'])
        else:need(not before['foreground'] and active==self.chooser['component'])
        uid_raw=self.shell('cmd','package','list','packages','-U','--user','0',package);owner=uid(uid_raw,package)
        if package!=PRIMARY:need(owner==self.chooser['uid'] and resolved(self.shell(*RESOLVE))==active)
        after_raw=self.shell('dumpsys','activity','activities');need(current(after_raw)==active)
        # UID assignment must still agree after the second actual Activity read.
        need(uid(self.shell('cmd','package','list','packages','-U','--user','0',package),package)==owner)
        value=dict(picoSnapshotOsSourceVersion=1,binding=deepcopy(self.binding),requestedEpochMs=requested,capturedEpochMs=0,
            component=active,uid=owner,foreground=before['foreground'],activityRaw=raw,activityAfterRaw=after_raw,activityFinalRaw='',uidRaw=uid_raw,
            activitySha256=hashlib.sha256(raw.encode()).hexdigest(),chooser=deepcopy(self.chooser))
        saved=deepcopy(value);result=deepcopy(value)
        captured,final,final_copy=self.finish(start,requested,before,active,owner,chooser=(self.chooser['component'],self.chooser['uid']))
        for row in (saved,result):row.update(capturedEpochMs=captured,activityFinalRaw=final['activityRaw'])
        saved['finalSource']=final;result['finalSource']=final_copy
        self.seal(start,requested);self.last=saved;return result

