"""World Web IME originals after a normal ray has independently gained focus."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,integer,need
from adapters.pico4.browser_source import IDENTITY,identity,geometry_original

VERSION=1


def validate_commit(packet,command):
    source=packet['source'];exact(source,{'delivered','focusRaw','nativeBeforeIME','imeEpochMs','nativeView'})
    need(type(source['delivered']) is bool and integer(source['imeEpochMs'],1,packet['capturedEpochMs']))
    view=source['nativeView'];exact(view,IDENTITY);identity(view)
    need(all(view[key]==command[key] for key in ('handle','creation','grant','page')))
    focused=geometry_original(source['focusRaw'],command,view['url'],source['imeEpochMs'],focused=True)
    before=source['nativeBeforeIME'];exact(before,{'text','cursor','anchor','absoluteCursor','kind','sensitive','focused','enabled'})
    need(type(before['text']) is str);units=len(before['text'].encode('utf-16-le'))//2
    need(units<=512 and integer(before['cursor'],0,units) and integer(before['anchor'],0,units)
        and type(before['absoluteCursor']) is int and before['absoluteCursor']==before['cursor']
        and before['kind']==('url' if command['control']=='foreign' else 'text')
        and before['sensitive'] is False and before['focused'] is True and before['enabled'] is True
        and all(before[key]==focused['editor'][key] for key in ('text','cursor','anchor')))
    return source


class PicoWorldTextInput:
    """One normal ray/focus/IME sequence with independent original readback.

    Durable phase and stream ownership belong to the enclosing caller. This
    object cannot recover or resend an uncertain gesture/commit from a file.
    """
    def __init__(self,click,commit_intent):
        from adapters.pico4.world_browser_ray import PicoWorldRayClick
        need(type(click) is PicoWorldRayClick and callable(commit_intent))
        self.click,self.io,self.commit_intent=click,click.io,commit_intent;self.issued=self.failed=False

    def replace(self,run,url,owner,view,text,*,control='text'):
        from copy import deepcopy
        from adapters.pico4.browser_source import geometry_original,command
        from adapters.native_feature_observation import number
        from adapters.normal_ui import NativeUIError
        from adapters.chat_journey.source_chunks import json_digest
        from adapters.script_journey.history import same
        need(not self.issued and not self.failed and control in ('text','foreign'))
        io=self.io;io.lock.assert_held();old_hook=io.before_send
        try:
            started=previous=io.monotonic();epoch=io.clock_ms()
            need(number(started,0,1e15) and integer(epoch,1))
            def bound():
                nonlocal previous
                now=io.monotonic();current=io.clock_ms()
                need(number(now,previous,started+5) and integer(current,epoch,epoch+5000));previous=now
            def measure():
                bound();packet=io.measure_ray(run,url,owner,view,control);bound()
                geometry=geometry_original(packet['source']['geometryRaw'],
                    dict(commandId=packet['commandId'],runId=run,control=control),view['url'],packet['capturedEpochMs'])
                return packet,geometry['editor']
            # Validate text before the first ordinary input. This uses the
            # existing closed protocol, not a generic keyboard/string setter.
            command(dict(schemaVersion=1,commandId='1'*32,action='pico-world-web',operation='commit-text',
                runId=run,fixtureUrl=url,ownerToken=owner,control=control,text=text,
                **{key:view[key] for key in ('handle','creation','grant','page')}))
            self.issued=True;gesture=self.click.click(run,url,owner,view,control);bound()
            for attempt in range(16):
                focus,editor=measure()
                if editor['focused']:break
                need(attempt<15);io.sleep(.1)
            else:need(False)
            original=deepcopy(focus);seal=json_digest(original);committed=False
            def before_send(call):
                nonlocal committed
                need(not committed and call['operation']=='commit-text' and json_digest(original)==seal)
                bound()
                if old_hook is not None:old_hook(deepcopy(call))
                self.commit_intent(dict(operation='world-browser-ime',command=deepcopy(call),focus=deepcopy(original)))
                bound();need(json_digest(original)==seal);committed=True
            io.before_send=before_send
            receipt=io.request(run,url,owner,'commit-text',control=control,text=text,
                **{key:view[key] for key in ('handle','creation','grant','page')})
            bound();need(committed and receipt['source']['delivered'] is True
                and receipt['source']['nativeView']=={key:view[key] for key in IDENTITY})
            io.before_send=old_hook
            for attempt in range(16):
                after,editor=measure()
                if editor['focused'] and editor['text']==text:break
                need(attempt<15);io.sleep(.1)
            else:need(False)
            # Full independent originals are returned, including the actual
            # observed text. No requested state or feature verdict is supplied.
            result=dict(gesture=gesture,commit=receipt,focusBefore=original,focusAfter=after)
            returned=deepcopy(result);bound();need(same(result,returned));bound();return returned
        except BaseException:
            self.failed=True
            raise NativeUIError('World Web text input is unresolved; original ownership remains') from None
        finally:io.before_send=old_hook
