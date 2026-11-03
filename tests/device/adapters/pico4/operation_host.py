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
    parent_pid=os.getppid();parent=process_identity(parent_pid);host=host_identity();adapter=None;seen=set();buffer=b''
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
    while True:
        guard()
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
            return 0
        value=request(value);identifier=value['requestId'];need(identifier not in seen and len(seen)<512);seen.add(identifier)
        now=guard();deadline=min(value['deadlineMonotonic'],now+timeout_for(value['operation']));need(now<deadline)
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
        result=adapter.invoke(args.target,value['operation'],value['arguments'])
        from contracts import validate_operation_result
        validate_operation_result(value['operation'],result);need(guard()<deadline)
        reply=dto_bytes(dict(picoOperationReplyVersion=VERSION,requestId=identifier,hostProcessIdentity=host,parentHostProcessIdentity=parent,result=result),RESPONSE_LIMIT)
        need(guard()<deadline)
        position=0
        while position<len(reply):
            need(guard()<deadline);_,writable,_=select.select([],[destination],[],min(.1,max(0,deadline-time.monotonic())))
            if writable:position+=os.write(destination,reply[position:position+4096])
        need(guard()<deadline)
