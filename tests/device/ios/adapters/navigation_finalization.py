"""Join an actual live seal to once-only process/SDK end and original archive.

No live feature observation is produced after Stop. Repeated finish is a pure
historical graph/OS/SDK-absence reconstruction with local candidate checks.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from feature_journeys import terminal as protocol
from ios.adapters.navigation_terminal import NavigationTerminal
from ios.adapters.navigation_process_end import NavigationProcessEnd
from ios.adapters.navigation_session_end import NavigationSessionEnd

VERSION=1


class NavigationFinalization:
    def __init__(self,terminal):
        need(type(terminal) is NavigationTerminal);self.terminal=terminal;self.flow=terminal.flow

    def finish(self,seal):
        terminal=self.terminal;f=self.flow
        with f.held():
            need(terminal.state is not None and same(terminal.store.read(),terminal.previous)
                and same(seal,terminal.state['seal']))
            protocol.sealed(seal,terminal.state['description'],terminal.state['samples'])
            store=PrivateFeatureState(f.store.path.with_name('ios-navigation-final-archive.json'));previous=store.read()
            if previous is not None:
                # A completed immutable archive is historical authority only.
                # Missing or rolled-back owners cannot start another source,
                # Stop, OS query or SDK operation while reconstructing it.
                need(PrivateFeatureState(f.store.path.with_name('ios-navigation-process-end.json')).read() is not None
                    and PrivateFeatureState(f.store.path.with_name('ios-navigation-session-end.json')).read() is not None)
            process=NavigationProcessEnd(terminal)
            from ios.adapters.navigation_terminal_replay import checked
            with checked(terminal,process.mutable()) as proof:
                process.checked_terminal=proof
                return self._finish(process,store,previous,seal)

    def _finish(self,process,store,previous,seal):
        terminal=self.terminal;f=self.flow
        if previous is None:
            if process.state is None:process.prepare()
            if process.state['phase']=='prepared':process.stop()
            while process.state['phase']!='complete':
                if process.advance():break
                f.clock();f.sleep(1.6);f.clock()
        process.verify();sdk=NavigationSessionEnd(process)
        if previous is None:sdk.finish()
        process.verify();sdk.historical()
        archive=dict(iosNavigationFinalArchiveVersion=VERSION,runId=f.run,artifactRoot=str(f.root),binding=process.binding,
            terminalOriginalSha256=digest(terminal.previous),processOriginalSha256=digest(process.previous),
            sdkOriginalSha256=digest(sdk.previous),sourceInventorySha256=digest(process.state['inventories']))
        if previous is None:store.write(archive,None)
        else:need(same(previous,archive))
        need(same(store.read(),archive));process.verify();sdk.historical()
        result=dict(featureTerminalEndVersion=1,seal=deepcopy(seal),roles={
            role:dict(binding=deepcopy(prior['binding']),heldOriginalSha256=prior['originalSha256'],
                stopOriginalSha256=digest(process.previous),osAbsence=process.role_os(role),
                sdkDeletionOriginalSha256=digest(sdk.previous),archiveSha256=digest(archive))
            for role,prior in terminal.state['description']['roles'].items()})
        protocol.ended(result,seal);f.clock();return result
