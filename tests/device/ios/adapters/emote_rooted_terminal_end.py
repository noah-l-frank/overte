"""Project fully replayed Emote end originals into the common terminal shape."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from feature_journeys.retirement_receipts import binding_from_context
from feature_journeys.terminal import os_quiet
from ios.adapters.emote_rooted_end_archive import IOSEmoteRootedEndArchive
from ios.adapters.emote_rooted_process_end import IOSEmoteRootedProcessEnd
from ios.adapters.emote_rooted_session_end import IOSEmoteRootedSessionEnd
from ios.adapters.process_retirement import IOSProcessRetirement


def role_end(process,session,archive):
    need(type(process) is IOSEmoteRootedProcessEnd and type(session) is IOSEmoteRootedSessionEnd
        and type(archive) is IOSEmoteRootedEndArchive and archive.state['phase']=='complete'
        and archive.processes[process.role] is process and archive.sessions[process.role] is session and session.process is process)
    archive.verify();process.completed();session.completed();state=process.os_state();raw=process.os_store().read()
    reader=object.__new__(IOSProcessRetirement);reader.profile='emote';reader.store=process.os_store()
    reader.binding=process.binding;reader.pid=int(process.binding['processIdentity']);reader.source=process.state['source']
    reader.bundle=process.state['bundleId'];reader.run=process.run;reader.role=process.role;reader.stage=0;reader._archives=None
    window=state['windows'][-1];need(window['complete'] and window['start'] is not None)
    rows=[reader.load(state['records'][n-1]) for n in window['samples'][window['start']:]]
    need(len(rows)>=3 and all(row['mode']=='observed' for row in rows));a,b=rows[0],rows[-1]
    quiet=dict(source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',instance=process.state['source']['instance'],
        processId=int(process.binding['processIdentity']),samples=len(rows),originalSha256=digest(dict(owner=raw,records=rows)),
        hostAfterFirstEpochMs=a['acquisition']['hostAfterEpochMs'],hostBeforeLastEpochMs=b['acquisition']['hostBeforeEpochMs'],
        hostAfterFirstMonotonic=a['acquisition']['hostAfterMonotonic'],hostBeforeLastMonotonic=b['acquisition']['hostBeforeMonotonic'],
        osAfterFirstEpochMs=a['original']['clockAfter']['epochMs'],osBeforeLastEpochMs=b['original']['clockBefore']['epochMs'],
        osAfterFirstMonotonicMs=a['original']['clockAfter']['monotonicMs'],osBeforeLastMonotonicMs=b['original']['clockBefore']['monotonicMs'])
    os_quiet(quiet,process.binding['processIdentity'])
    return dict(binding=binding_from_context(process.binding),heldOriginalSha256=archive.seal['description']['roles'][process.role]['originalSha256'],
        stopOriginalSha256=digest(process.previous),osAbsence=quiet,sdkDeletionOriginalSha256=digest(session.previous),archiveSha256=digest(archive.previous))
