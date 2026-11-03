"""Explicit host producers for the real Browser Actor6 entrypoint in tests.

The actual entrypoint, admission, observer loop and actor return are retained.
Candidate admission and the product-source facade are declared model seams.
This module is loaded only by a task-owned Python startup file in the test.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
from types import MethodType, SimpleNamespace


def install():
    import atexit
    from self_tests.pico_browser_coordinator_worker import sources,finish_sources
    before=sources()
    atexit.register(finish_sources,before,'actor')
    from adapters.android import adapter
    from adapters.pico4.tablet_web_binding import PicoTabletWebBinding
    from adapters.script_journey.lock import ScriptSourceLock
    from contextlib import contextmanager
    from self_tests.pico_browser_process_fixture import IndependentBrowserSources
    root = Path(os.environ['OVT_BROWSER_COORDINATOR_MODEL_ROOT'])
    config = json.loads((root/'native-model.json').read_text())
    original_new = PicoTabletWebBinding.__new__
    held=ScriptSourceLock.held
    @contextmanager
    def diagnostic_held(lock):
        import time
        requested=time.monotonic()
        with held(lock):
            acquired=time.monotonic()
            try:yield
            except BaseException as error:
                import traceback
                with (root/'actor-original-lock-failure.txt').open('a') as stream:
                    stream.write(traceback.format_exc())
                trace=error.__traceback__
                while trace is not None:
                    frame=trace.tb_frame
                    if frame.f_code.co_filename.endswith('/pico4/browser_quiet.py') and frame.f_code.co_name=='validate':
                        # Diagnostic DTO only: never fresh raw/provider evidence.
                        (root/'actor-rejected-quiet-diagnostic.json').write_text(json.dumps(frame.f_locals['value']))
                    trace=trace.tb_next
                raise
            finally:
                with (root/'actual-source-lock-intervals.jsonl').open('a') as stream:
                    stream.write(json.dumps(dict(pid=os.getpid(),requested=requested,acquired=acquired,released=time.monotonic()))+'\n')
    ScriptSourceLock.held=diagnostic_held

    def allocate(cls, original):
        if type(original) is IndependentBrowserSources:
            original.feature = MethodType(PicoTabletWebBinding.feature, original)
            return original
        return original_new(cls)

    def create(_candidate, _base):
        return IndependentBrowserSources(config)

    def cli(arguments):
        assert arguments == ['--kind', 'pico', '--native-binding', '--declared-host-model',
            'describe', '--target', 'target']
        return SimpleNamespace(native_binding=True, kind='pico', action='describe',
            target='target', operation=None, arguments='{}'), SimpleNamespace(create_adapter=create)

    PicoTabletWebBinding.__new__ = staticmethod(allocate)
    adapter.cli = cli
