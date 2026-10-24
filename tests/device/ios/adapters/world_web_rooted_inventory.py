"""Paired World ownership census over successfully decoded actual originals.

Names select responsibility, never qualify a carrier. Only exact typed terminal
outputs may change during a journal commit. Process/SDK outputs need their own
successful original readers and a new readonly census after their transition.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import stat

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import record
from adapters.script_feature.history import same
from adapters.script_feature.history import same
from ios.adapters.emote_original_lease import EmoteOriginalLease

PREFIXES=('ios-world-web-','ios-worldweb-','world-web-',
    'worldweb-marker-read-abandoned-','wwc-','wwrg-','wwsu-',
    'phase-publication-world-web-','phase-retirement-world-web-',
    'graphics-world-frame-','vulkan-world-')


def inventory(roots):
    """Include files of every suffix, nested carriers and ambiguous GPU owners."""
    need(type(roots) is set and 1<=len(roots)<=4)
    found=set();seen=set()
    def visit(path,depth):
        need(depth<=64 and len(seen)<50000)
        if path in seen:return
        seen.add(path);before=path.lstat()
        if stat.S_ISDIR(before.st_mode):
            need(before.st_uid==os.geteuid())
            with os.scandir(path) as rows:names=sorted(row.name for row in rows)
            for name in names:visit(path/name,depth+1)
        else:
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==os.geteuid())
            if path.name.startswith(PREFIXES):found.add(path)
        need(EmoteOriginalLease.signature(before)==EmoteOriginalLease.signature(path.lstat()))
    for root in sorted(roots):
        need(isinstance(root,Path) and root.is_absolute() and root.resolve(strict=True)==root)
        PrivateFeatureState(root/'boundary')._parent();visit(root,0)
    return found


class WorldWebRootedInventory:
    def __init__(self,terminal,reads):
        from ios.adapters.world_web_terminal import WorldWebTerminal
        need(type(terminal) is WorldWebTerminal and type(reads) is set)
        self.terminal=terminal;self.roots=self.current_roots()
        found=inventory(self.roots);owned=self.owned()
        need(found<=reads|owned)
        self.paths=found-owned
        self.signatures={path:EmoteOriginalLease.signature(path.lstat()) for path in self.paths}
        self.guard()

    def current_roots(self):
        terminal=self.terminal;roots=set()
        for flow in (terminal.flow,terminal.actor):
            flow.lock.assert_held();flow.primary_lock.assert_held()
            need(flow.run==terminal.flow.run)
            roots.update((flow.root,flow.store.path.parent))
        return roots

    def owned(self):
        """No name-wide exemption: reopen the exact typed original references."""
        terminal=self.terminal;terminal.guard();result={terminal.store.path}
        if terminal.state is None:return result
        terminal.decode(terminal.envelope(terminal.state))
        need(terminal.frames is not None)
        for index,reference in enumerate(terminal.state['records'],1):
            terminal.private(index)
            result.add(terminal.frames.path(terminal.frames.expand(reference)))
        pending=terminal.state['pending']
        if pending is not None:
            terminal.frames.original(pending);path=terminal.frames.path(pending)
            if pending['phase']=='planned':need(not os.path.lexists(path))
            else:terminal.frames.read(pending)
            result.add(path)
        return result

    def guard(self):
        need(self.current_roots()==self.roots)
        need(inventory(self.roots)-self.owned()==self.paths)
        for path,signature in self.signatures.items():
            PrivateFeatureState(path)._parent()
            need(EmoteOriginalLease.signature(path.lstat())==signature);record(path)
        return True


def read_current_end(terminal,parts):
    """Decode retained partial end ownership without acquiring a current fact.

    A scene archive needs a fully readable observed original, even when its
    final metadata CAS is pending. Unknown or partial birth fails closed. OS
    pending records are accepted only by their existing pure original decoder;
    unknown file birth or an unowned OS/SDK file is never admitted by a name.
    """
    from adapters.native_clock_join import digest
    from ios.adapters.process_retirement import IOSProcessRetirement,filename
    from ios.adapters.world_web_final_archive import WorldWebFinalArchive
    from ios.adapters.world_web_process_end import WorldWebProcessEnd
    from ios.adapters.world_web_session_end import WorldWebSessionEnd
    from ios.adapters.world_web_terminal import WorldWebTerminal
    from ios.adapters import world_web_fence as fence
    need(type(terminal) is WorldWebTerminal and type(parts) is dict and set(parts)=={'primary','actor'})
    terminal.guard();roots=set()
    for flow in (terminal.flow,terminal.actor):
        flow.lock.assert_held();flow.primary_lock.assert_held()
        roots.update((flow.root,flow.store.path.parent))
    leases=[EmoteOriginalLease(root,[]) for root in roots]
    for flow in (terminal.flow,terminal.actor):
        component=parts[flow.role];process=WorldWebProcessEnd(flow)
        scene=WorldWebFinalArchive(flow.runtime._world_web_store(flow.selector,
            'ios-world-web-'+flow.role+'-'+flow.run+'-final.json'),flow.root,flow.state['binding'],flow.run,flow.role,flow.lock)
        sdk_store=flow.runtime._world_web_store(flow.selector,'ios-world-web-'+flow.role+'-'+flow.run+'-sdk-final.json')
        sdk_raw=sdk_store.read();sdk=None
        if process.state is None:
            need(scene.previous is None and sdk_raw is None)
            continue
        original=fence.original(component['retirement'])
        need(digest(original)==process.state['sceneSha256'])
        if process.state['fence'] is not None:fence.validate(process.state['fence'],flow,component)
        if scene.previous is not None:
            need(process.state['phase']=='complete')
            frame=scene.verify() if scene.state['phase']=='complete' else scene.pending_original()
            header={key:value for key,value in flow.previous.items() if key!='payload'}
            need(same(frame['feature'],dict(flow.state,phase=frame['feature']['phase']))
                and same(frame['coordinatorHeader'],header) and digest(frame['original'])==process.state['sceneSha256']
                and same(component['retirement'].validate_original(frame['original']),frame['measured']))
        if sdk_raw is not None:
            need(flow.state['phase']=='retired' and process.state['phase']=='complete'
                and scene.previous is not None and scene.state['phase']=='complete')
            sdk=WorldWebSessionEnd.archive(sdk_raw,root=flow.root,binding=flow.state['binding'],run=flow.run,role=flow.role)
            need(sdk['processSha256']==digest(process.previous) and sdk['sceneSha256']==digest(scene.previous))
        for stage in (0,1):
            store=PrivateFeatureState(process.store.path.with_name(filename('worldweb',flow.role,stage)));raw=store.read()
            if raw is None:continue
            need(process.state['phase']!='fencing' and (stage==0 or sdk is not None))
            IOSProcessRetirement.archive(raw,path=store.path,binding=flow.state['binding'],source=process.state['source'],
                bundle=process.state['bundleId'],run=flow.run,role=flow.role,stage=stage,profile='worldweb')
        process.bound();need(same(scene.store.read(),scene.previous) and same(sdk_store.read(),sdk_raw))
    terminal.guard()
    for lease in leases:lease.guard()
