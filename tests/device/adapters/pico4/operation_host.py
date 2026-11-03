"""One original bound adapter on stdio; no discovery, service or cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import select
import sys
import time
from adapters.host_process_identity import host_identity
from adapters.pico4.operation_protocol import (VERSION,REQUEST_LIMIT,RESPONSE_LIMIT,STRIPPED_ENV,need,decode,dto_bytes,request,timeout_for)


def process_identity(pid):
    from pathlib import Path
    fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    need(fields[0] not in ('Z','X'))
    return str(pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def serve(args,binding,base_class,construct,*,profiles,stdin=None,stdout=None):
    """Called only by the existing Android main BEFORE its normal factory.

    Read the first bounded request before constructing the SAME normal factory.
    Per-request DTOs never become argparse/environment/cwd mutations.
    """
    need(args.kind=='pico' and args.native_binding and binding is not None and args.action=='operation-host'
        and type(args.target) is str and bool(args.target) and args.operation is None and args.arguments=='{}')
    need(all(key not in os.environ for key in STRIPPED_ENV))
    original_args=dto_bytes({key:str(value) for key,value in vars(args).items()},REQUEST_LIMIT)
    original_types={key:type(value) for key,value in vars(args).items()};admitted_fields=dict(vars(args));environment=dict(os.environ);cwd=os.getcwd()
    parent_pid=os.getppid();parent=process_identity(parent_pid);host=host_identity();adapter=None;seen=set();buffer=b'';create_owner=None;browser_owner=None
    source=sys.stdin.fileno() if stdin is None else stdin;destination=sys.stdout.fileno() if stdout is None else stdout
    started=last=time.monotonic();lifetime=started+1560
    def guard():
        nonlocal last
        now=time.monotonic();need(last<=now<lifetime);last=now
        need(os.getppid()==parent_pid and process_identity(parent_pid)==parent and host_identity()==host
            and dict(os.environ)==environment and os.getcwd()==cwd
            and {key:type(value) for key,value in vars(args).items()}==original_types
            and dto_bytes({key:str(value) for key,value in vars(args).items()},REQUEST_LIMIT)==original_args)
        return now
    try:
        while True:
            guard()
            if create_owner is not None:create_owner.control()
            if browser_owner is not None:browser_owner.control()
            if b'\n' not in buffer:
                ready,_,_=select.select([source],[],[],min(.1,max(0,lifetime-time.monotonic())))
                if not ready:continue
                chunk=os.read(source,min(4096,REQUEST_LIMIT-len(buffer)+1))
                if not chunk:
                    # EOF without the explicit owned Close frame is uncertain.
                    need(False)
                buffer+=chunk;need(len(buffer)<=REQUEST_LIMIT)
                if b'\n' not in buffer:continue
            raw,buffer=buffer.split(b'\n',1);need(not buffer) # Sequential requests only.
            value=decode(raw+b'\n',REQUEST_LIMIT)
            if set(value)=={'picoOperationCloseVersion','requestId','deadlineMonotonic'}:
                need(type(value['picoOperationCloseVersion']) is int and value['picoOperationCloseVersion']==1
                    and type(value['requestId']) is str and len(value['requestId'])==32 and all(ch in '0123456789abcdef' for ch in value['requestId']) and value['requestId'] not in seen
                    and type(value['deadlineMonotonic']) in (int,float) and adapter is not None and guard()<value['deadlineMonotonic'])
                if create_owner is not None:create_owner.close_host()
                if browser_owner is not None:browser_owner.close_host()
                return 0
            browser_private='picoBrowserOperationRequestVersion' in value
            private=browser_private or 'picoCreateOperationRequestVersion' in value
            if browser_private:
                from adapters.pico4.browser_operation_protocol import validate
                value=validate(value)
            elif private:
                from adapters.pico4.create_operation_protocol import validate
                value=validate(value)
            else:value=request(value)
            identifier=value['requestId'];need(identifier not in seen and len(seen)<512);seen.add(identifier)
            now=guard();selected=value['actionBudget']['deadlineMonotonic'] if browser_private else value['budget']['deadlineMonotonic'] if private else value['deadlineMonotonic']
            deadline=min(selected,now+timeout_for(value['operation']));need(now<deadline)
            if adapter is None:
                # The existing Pico factory adds its original require_identity flag
                # once during admission. Freeze only after that authorized factory.
                adapter=construct(args,binding,base_class,args.kind)
                need(adapter.kind==args.kind and adapter.profile==profiles[args.kind])
                current=dict(vars(args));expected=dict(admitted_fields)
                if current.get('require_identity') is True:expected['require_identity']=True
                need(current==expected and all(type(current[key]) is type(item) for key,item in expected.items()))
                original_args=dto_bytes({key:str(item) for key,item in vars(args).items()},REQUEST_LIMIT)
                original_types={key:type(item) for key,item in vars(args).items()}
            need(guard()<deadline)
            if browser_private:
                need(create_owner is None)
                if browser_owner is None:
                    need(value['operation']=='begin')
                    browser_owner=adapter._browser_operation_owner(args.target,value,parent)
                    adapter._browser_operation_active=browser_owner
                result=browser_owner.dispatch(value)
                reply_value=dict(picoBrowserOperationReplyVersion=1,requestId=identifier,hostProcessIdentity=host,parentHostProcessIdentity=parent,
                    componentOnly=True,completeCommonObservation=False,result=result)
            elif private:
                need(browser_owner is None)
                if create_owner is None:create_owner=adapter._create_operation_owner(args.target,value['runId'],value['fixtureUrl'])
                result=create_owner.dispatch(value)
                reply_value=dict(picoCreateOperationReplyVersion=1,requestId=identifier,hostProcessIdentity=host,parentHostProcessIdentity=parent,
                    componentOnly=True,completeCommonObservation=False,result=result)
            else:
                if create_owner is not None:need(value['operation'] in ('app.process','app.foreground','probe.snapshot','telemetry.snapshot'))
                from contracts import validate_operation_result
                if browser_owner is not None and value['operation'].startswith('feature.tablet-web.'):
                    with browser_owner.public_context(value):
                        result=adapter.invoke(args.target,value['operation'],value['arguments'])
                        validate_operation_result(value['operation'],result)
                else:
                    if browser_owner is not None:
                        allowed=('app.process','app.foreground','probe.snapshot','telemetry.snapshot')
                        if browser_owner.worker is None:allowed+=('scene.load',)
                        need(value['operation'] in allowed)
                    result=adapter.invoke(args.target,value['operation'],value['arguments'])
                    validate_operation_result(value['operation'],result)
                reply_value=dict(picoOperationReplyVersion=VERSION,requestId=identifier,hostProcessIdentity=host,parentHostProcessIdentity=parent,result=result)
            need(guard()<deadline)
            reply=dto_bytes(reply_value,RESPONSE_LIMIT)
            need(guard()<deadline)
            position=0
            while position<len(reply):
                need(guard()<deadline);_,writable,_=select.select([],[destination],[],min(.1,max(0,deadline-time.monotonic())))
                if writable:position+=os.write(destination,reply[position:position+4096])
            need(guard()<deadline)
    finally:
        if create_owner is not None:
            try:create_owner.unwind()
            except Exception:pass
        if browser_owner is not None:
            try:browser_owner.unwind()
            except Exception:pass
