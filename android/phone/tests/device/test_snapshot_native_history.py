"""Compile the passive history component with real Qt6 and original clocks.

This checks native recorder behavior, not the complete Android Snapshot client.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
SOURCE=r'''
#include <QCoreApplication>
#include "tests/device/native/PhoneSnapshotHistory.h"
using overte::e2e::PhoneSnapshotHistory;
int main(int argc,char** argv) {
    QCoreApplication application(argc,argv);PhoneSnapshotHistory history;
    const auto mode=QString::fromLocal8Bit(argv[1]);
    if (mode=="disabled") {
        history.record("capture-begin","snap_1");return history.snapshot().isEmpty() ? 0 : 1;
    }
    const auto initial=history.snapshot();
    if (initial.value("complete")!=true || initial.value("sequence")!=0) { return 2; }
    if (mode=="overflow") {
        for(int index=0;index<256;++index) { history.record("capture-begin","snap_"+QString::number(index)); }
        if (history.snapshot().value("complete")!=true) { return 3; }
        history.record("capture-begin","snap_overflow");auto result=history.snapshot();
        return result.value("complete")==false && result.value("events").toList().size()==256 ? 0 : 4;
    }
    if (mode=="invalid") {
        history.record("capture-begin","snap_1");history.record("capture-status","snap_1","invented-success");
        history.record("capture-status","snap_1","complete","/private/Snapshots/image.png");
        const auto result=history.snapshot();
        return result.value("complete")==false && result.value("events").toList().size()==1 ? 0 : 5;
    }
    history.record("capture-begin","snap_1");history.record("capture-status","snap_1","processing","/private/Snapshots/image.png");
    history.record("capture-status","snap_1","cancelled");
    history.record("upload-begin","/private/Snapshots/image.png",{},"/private/Snapshots/image.png");
    history.record("upload-status","/private/Snapshots/image.png","error","/private/Snapshots/image.png","upload-failed");
    auto result=history.snapshot();auto rows=result.value("events").toList();
    if (result.value("complete")!=true || result.value("sequence")!=5 || rows.size()!=5
            || result.value("instance")!=initial.value("instance")) { return 6; }
    qint64 previous=0,elapsed=0;
    for(int index=0;index<rows.size();++index) {
        const auto row=rows[index].toMap();
        if (row.value("sequence")!=index+1 || row.value("capturedEpochMs").toLongLong()<previous
                || row.value("capturedEpochMs").toLongLong()>QDateTime::currentMSecsSinceEpoch()
                || row.value("elapsedMs").toLongLong()<elapsed) { return 7; }
        previous=row.value("capturedEpochMs").toLongLong();elapsed=row.value("elapsedMs").toLongLong();
    }
    if (rows[2].toMap().value("phase")!="cancelled" || rows[4].toMap().value("error")!="upload-failed") { return 8; }
    rows.clear();result["complete"]=false;
    return history.snapshot().value("complete")==true && history.snapshot().value("events").toList().size()==5 ? 0 : 9;
}
'''


class SnapshotNativeHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build=ROOT/'build/snapshot-native-contract';build.mkdir(parents=True,exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(prefix='history-',dir=build);cls.addClassCleanup(cls.temporary.cleanup)
        stage=Path(cls.temporary.name);cpp=stage/'source.cpp';cpp.write_text(SOURCE);cls.binary=stage/'check'
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
            '-I'+str(ROOT),str(cpp),'-o',str(cls.binary),*flags],check=True,timeout=60)

    def run_case(self,mode,enabled=True):
        subprocess.run([str(self.binary),mode,*(['--testScript'] if enabled else [])],check=True,timeout=5)
    def test_original_events_and_clocks_cannot_be_changed_through_a_returned_copy(self):self.run_case('events')
    def test_missing_test_script_flag_disables_recording_and_observation(self):self.run_case('disabled',False)
    def test_overflow_preserves_original_prefix_and_permanently_marks_incomplete(self):self.run_case('overflow')
    def test_unknown_native_phase_never_enters_a_successful_history(self):self.run_case('invalid')


if __name__=='__main__':unittest.main()
