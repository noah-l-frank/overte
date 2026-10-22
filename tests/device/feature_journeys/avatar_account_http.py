"""Closed private Avatar authority preparation routes on the existing fixture."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from feature_journeys.contract import exact,identifier


def handle(handler,parts,body,*,reader,actor,adapter_reader):
    if len(parts)<3 or parts[0]!='runs' or parts[2]!='avatar':return False
    scopes=getattr(handler.server,'avatar_accounts',None);run=identifier(parts[1])
    if (scopes is None or run not in handler.server.journal.runs
            or handler.server.journal.runs[run]['area']!='avatar-people'):
        handler.send(404,{'error':'not-found'});return True
    route=parts[3:]
    if handler.command=='GET' and route==['accounts'] and (reader or adapter_reader):
        handler.send(200,scopes.snapshot(run));return True
    if handler.command=='GET' and len(route)==2 and route[0]=='credentials' and (reader or adapter_reader):
        handler.send(200,scopes.credentials(run,route[1]));return True
    if handler.command=='GET' and len(route)==4 and route[0]=='proof' and actor:
        handler.send(200,scopes.profile_proof(run,route[1],route[2],route[3]));return True
    if handler.command=='POST' and route==['sessions'] and reader:
        exact(body,{'sessions','domain'},'Avatar session preparation')
        scopes.bind_sessions(run,body['sessions'],body['domain']);handler.send(200,{});return True
    if handler.command=='POST' and route==['control'] and reader:
        exact(body,{'operation'},'Avatar authority control')
        if body['operation']!='revoke':raise ValueError('Unknown Avatar authority control')
        scopes.revoke(run);handler.send(200,{});return True
    handler.send(403,{'error':'forbidden'});return True
