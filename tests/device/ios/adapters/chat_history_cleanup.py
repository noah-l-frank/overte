"""Normal Erase/rebuild of an originally null private Chat history.

No setting setter, native handler call, peer effect or resource-end shortcut.
Other original representations remain owned when normal Erase cannot restore
their exact native value. Journals and source/session responsibility remain.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from feature_journeys.contract import identifier
from ios.adapters.chat_history_value import unchanged_empty


def final_result(owner,ticket):
    rows=[op for op in owner.state['operations'] if op['ticket']==ticket and op['verb']=='cleanup']
    need(len(rows)==1 and owner.state['pending'] is owner.state['observation'] is None)
    op=rows[0];owner.quiet(op);frame=owner.original(op['after']);local=owner.local(frame)
    need(not local['open'] and not local['draft'] and not local['focused'] and not local['keyboard'])
    steps={step['verb']:step for step in owner.state['operations'] if step['ticket']==ticket}
    if 'cleanup-erase' in steps:
        need('cleanup-rebuild-close' in steps and 'cleanup-rebuild-open' in steps)
        erase,closed,opened=(steps[key] for key in ('cleanup-erase','cleanup-rebuild-close','cleanup-rebuild-open'))
        need(erase['after']['index']<closed['before']['index']<closed['after']['index']
            <opened['before']['index']<opened['after']['index']<op['before']['index'])
    baseline=owner.original(owner.state['baseline'])['originals']['view']
    need(baseline['source']['storage']['kind']=='null');unchanged_empty(baseline,frame['originals']['view'])
    return dict(verifiedDraftAction='cleanup',historyRestored=True,original=deepcopy(op['after']),local=local,failed=bool(owner.state['failures']))


def restore(owner,ticket):
    from ios.adapters.chat_draft_owner import IOSChatDraftOwner,RESTORE_STEPS,RESTORE_READ
    need(type(owner) is IOSChatDraftOwner and owner.version>=3);identifier(ticket);owner.bound()
    if any(op['ticket']==ticket and op['verb']=='cleanup' for op in owner.state['operations']):return final_result(owner,ticket)
    need(not owner.historical);owner.recover_observation()
    if owner.state['pending'] is not None:
        pending=owner.state['pending']
        if pending['verb'] in RESTORE_STEPS|{'cleanup'}:
            need(pending['ticket']==ticket);owner.resolve()
            if pending['verb']=='cleanup':return final_result(owner,ticket)
        else:
            need(len(owner.state['failures'])<32);owner.state['failures'].append(deepcopy(pending))
            owner.state['pending']=None;owner.save()
    reference=owner.capture(ticket,RESTORE_READ,{})
    if owner.state['baseline'] is None:
        owner.baseline(owner.original(reference));owner.state['baseline']=deepcopy(reference);owner.save()
    baseline=owner.original(owner.state['baseline'])['originals']['view']
    need(baseline['chatViewVersion']>=2 and baseline['source']['storage']['kind']=='null')
    frame=owner.original(reference);local=owner.local(frame);need(frame['originals']['view']['chatViewVersion']>=2)
    if local['draft']:
        owner.act(ticket,'cleanup-discard',{});reference=owner.capture(ticket,RESTORE_READ,{})
        frame=owner.original(reference);local=owner.local(frame)
    erased=any(op['ticket']==ticket and op['verb']=='cleanup-erase' for op in owner.state['operations'])
    if frame['originals']['view']['source']['storage']['count']:
        if not local['open']:
            owner.act(ticket,'cleanup-open',{});reference=owner.capture(ticket,RESTORE_READ,{})
            frame=owner.original(reference);local=owner.local(frame)
        if local['channel']!='settings':owner.act(ticket,'cleanup-settings',{})
        owner.act(ticket,'cleanup-erase',{});erased=True
    if erased:
        # Rebuilding the real page must read the Script's real messageHistory.
        # Empty Settings/ListModels alone cannot prove that internal history
        # was cleared. Distinct durable steps share the original cleanup phase.
        closed=any(op['ticket']==ticket and op['verb']=='cleanup-rebuild-close' for op in owner.state['operations'])
        opened=any(op['ticket']==ticket and op['verb']=='cleanup-rebuild-open' for op in owner.state['operations'])
        if not closed:owner.act(ticket,'cleanup-rebuild-close',{})
        if not opened:owner.act(ticket,'cleanup-rebuild-open',{})
    # A final normal close owns its original three advancing quiet cuts. It
    # also preserves failed-action status and all source/SDK responsibility.
    owner.act(ticket,'cleanup',{});return final_result(owner,ticket)
