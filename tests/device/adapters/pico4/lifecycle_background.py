"""Original Lifecycle background evidence; normal OS input remains separate.

Historical validation is pure and usable while foreground native guards are
unavailable. A current observation always needs fresh original readers again.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import LIMIT,decode,exact,need
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import context
from adapters.pico4 import lifecycle_background_source as history,lifecycle_source as ui
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_process import native,settings,identity
from feature_journeys.fixtures import context as fixture


def bytes_packet(value):
    exact(value,{'raw','sha256'});need(type(value['raw']) is str and len(value['raw'].encode('utf-8'))<=LIMIT
        and frame(value['raw'])==value)
    return decode(value['raw'])


def original(value,validator,pid,run):
    """Validate original bytes and hash without calling a clock or a client."""
    packet=bytes_packet(value);need(packet['runId']==run)
    validator(packet,packet,pid,packet['capturedEpochMs']);return packet


def source_original(value,pid,run):
    packet=bytes_packet(value);need(packet['runId']==run)
    operation='observe'
    if packet['performed']:operation='arm' if packet['commandId']==packet['armCommandId'] else 'release'
    request=dict(schemaVersion=1,commandId=packet['commandId'],runId=run,action='feature-lifecycle-background',operation=operation)
    if operation!='observe':request.update(ownerInstance=packet['instance'],intentSequence=packet['lastIntentSequence'])
    history.validate(packet,request,pid,packet['capturedEpochMs']);return packet


def feature_original(value,pid):
    return native(bytes_packet(value),pid)


def status(value,binding,foreground):
    exact(value,{'binding','running','foreground'})
    need(context(value['binding'])==binding and value['running'] is True and value['foreground'] is foreground)


def compact_quiet(value):
    need(value['created'] and value['enabled'] and value['keyCount']>0
        and not value['visible'] and not value['raised'] and value['pressedKeys']==0)


def same_editor(before,after):
    need(all(before[key]==after[key] for key in ui.IDENTITIES)
        and all(after[key] for key in ui.LIVENESS) and after['alive'])


def chat_current(packet,run,*,quiet):
    row=ui.current_editor(packet)
    need(row is not None and row['kind']=='chat' and row['visible'] and row['attached']
        and row['text']==fixture(run)['reply'] and packet['source']['tabletShown'] and not packet['source']['onHomeScreen'])
    if quiet:
        keyboard=packet['source']['keyboard']
        need(not row['focused'] and not any(item['focused'] for item in packet['source']['editors'])
            and measured_keyboard(keyboard) is False and keyboard['created'] and keyboard['enabled'])
    return row


def advanced(before,after):
    need(after['instance']==before['instance'] and after['sequence']>before['sequence']
        and after['requestedEpochMs']>=before['capturedEpochMs'] and after['capturedEpochMs']>=before['capturedEpochMs']
        and settings(after)==settings(before))
    a,b=before['lifecycle'],after['lifecycle']
    need(b['backgrounds']>=a['backgrounds']+1 and b['activations']>=a['activations']+1 and b['launches']==a['launches'])


def validate_return(value,run,binding):
    """Join OS identity, native lifecycle and immutable Qt history originals.

    No acknowledgement, requested keyboard state or resumed-only observation
    substitutes for the independently observed Hidden/Suspended interval.
    """
    exact(value,{'beforeUi','beforeNative','home','background','foreground','returned','afterUi','afterNative','arm'})
    pid,_start=identity(binding);need(ui.nonce(run))
    before=original(value['beforeUi'],ui.validate,pid,run);after=original(value['afterUi'],ui.validate,pid,run)
    old=chat_current(before,run,quiet=False);current=chat_current(after,run,quiet=True)
    same_editor(old,current);ui.accept(ui.summary(before),ui.summary(after))
    first,last=feature_original(value['beforeNative'],pid),feature_original(value['afterNative'],pid);advanced(first,last)
    home=source_original(value['home'],pid,run);returned=source_original(value['returned'],pid,run)
    history.command(value['arm']);arm=value['arm']
    need(arm['operation']=='arm' and arm['runId']==run and home['available'] and returned['available']
        and home['active'] and home['timerActive'] and not home['released']
        and returned['active'] and returned['timerActive'] and not returned['released']
        and all(packet['ownerRunId']==run and packet['originalId']==old['id']
            and packet['instance']==arm['ownerInstance'] and packet['armCommandId']==arm['commandId']
            and packet['lastIntentSequence']==arm['intentSequence'] for packet in (home,returned)))
    history.accept(home,returned);status(value['background'],binding,False);status(value['foreground'],binding,True)
    initial=home['frames'][0];boundary=home['frames'][-1]
    need(initial['uiInstance']==before['instance'] and initial['uiSequence']>before['sequence']
        and initial['uiCapturedEpochMs']>=before['capturedEpochMs']
        and initial['keyboard']['instance']==before['source']['keyboard']['instance']
        and initial['keyboard']['sequence']>before['source']['keyboard']['sequence']
        and home['capturedEpochMs']>=first['capturedEpochMs'] and boundary['applicationState']=='active')
    same_editor(old,initial['editor']);need(initial['editor']['text']==old['text'])
    later=returned['frames'][len(home['frames']):];hidden=[];resumed=[]
    for index,row in enumerate(later):
        same_editor(old,row['editor']);need(row['currentId'] in ('',old['id']))
        if row['applicationState'] in ('hidden','suspended'):
            need(row['capturedEpochMs']>=home['capturedEpochMs'] and row['signalSequence']>boundary['signalSequence']
                and row['focusedEditors']==0 and not row['editor']['focused'])
            compact_quiet(row['keyboard']);hidden.append(index)
        if hidden and index>hidden[0] and row['applicationState']=='active':
            need(row['signalSequence']>later[hidden[0]]['signalSequence'] and row['editor']['current']
                and row['editor']['text']==fixture(run)['reply'] and row['focusedEditors']==0 and not row['editor']['focused'])
            compact_quiet(row['keyboard']);resumed.append(index)
    need(hidden and resumed)
    # Once the actual native return is seen, focus/keyboard must remain quiet.
    for row in later[resumed[0]:]:
        need(row['applicationState']=='active' and row['editor']['current'] and row['editor']['visible']
            and row['editor']['text']==fixture(run)['reply'] and not row['editor']['focused'] and row['focusedEditors']==0)
        compact_quiet(row['keyboard'])
    final=returned['frames'][-1]
    need(after['instance']==final['uiInstance'] and after['sequence']>final['uiSequence']
        and after['capturedEpochMs']>=returned['capturedEpochMs']
        and after['source']['keyboard']['instance']==final['keyboard']['instance']
        and after['source']['keyboard']['sequence']>final['keyboard']['sequence']
        and last['requestedEpochMs']>=after['capturedEpochMs'])
    return dict(editor='chat',text=current['text'],generation=2,focused=False,keyboard=False,
        originalId=current['id'],nativeBackgroundFrames=len(hidden),nativeReturnFrames=len(resumed),journalRetained=True)
