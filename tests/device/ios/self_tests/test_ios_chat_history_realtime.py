"""Real host clocks/quiet waits around declared native/Qt/transport models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
import unittest
from ios.self_tests.test_ios_chat_history_cleanup import ChatHistoryCleanupTests,RestoreModel
from ios.self_tests.test_ios_chat_settings_controls import SettingsWidgets


class RealClockWidgets(SettingsWidgets):
    def __init__(self):
        self.born=time.monotonic();super().__init__()
    @property
    def clock(self):return time.monotonic()
    @clock.setter
    def clock(self,value):pass
    @property
    def elapsed(self):return 100+int((time.monotonic()-self.born)*1000)
    @elapsed.setter
    def elapsed(self,value):pass
    def sleep(self,seconds):time.sleep(seconds)


class RealClockRestoreModel(RestoreModel):
    def __init__(self):
        self.born=time.monotonic();super().__init__();old=self.widgets;self.widgets=RealClockWidgets()
        self.widgets.pid,self.widgets.instance,self.widgets.generation=old.pid,old.instance,old.generation
        capture=self.widgets.capture
        def original():
            value=capture()
            for row in value['controls']:
                if row['id'].startswith('tablet.'):row.pop('inputReady',None)
            return value
        self.widgets.capture=original
    def tick(self):pass
    def epoch(self):return int(time.time()*1000)
    def native_epoch(self):return 100000+int((time.monotonic()-self.born)*1000)


class ChatHistoryRealtimeTests(unittest.TestCase):
    def test_normal_erase_rebuild_close_stays_in_one_real_twenty_second_budget(self):
        f=ChatHistoryCleanupTests();f.setUp();self.addCleanup(f.doCleanups)
        f.m=f.f.model=RealClockRestoreModel();f.message();f.action('close');f.phase()
        started=time.monotonic();result=f.restore();elapsed=time.monotonic()-started
        self.assertTrue(result['historyRestored']);self.assertFalse(result['failed'])
        self.assertGreaterEqual(elapsed,6.4);self.assertLess(elapsed,20)
        self.assertEqual(1,f.m.erases)
        with f.archive() as owner:
            original=owner.original(result['original']);join=original['clockJoin']
            self.assertGreater(join['hostBeforeEpochMs']-join['nativeBefore']['capturedEpochMs'],1000000000000)
            owner.quiet(owner.state['operations'][-1])


if __name__=='__main__':unittest.main()
