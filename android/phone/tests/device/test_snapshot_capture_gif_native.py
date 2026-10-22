"""Original GIF worker compiled against a prepared real GifCreator dependency.

Actual Qt images/GIF codec/FILE close/inodes/unlink; original worker function is
extracted unchanged. Capture scheduling and mid-worker cancellation are explicit
host seams. This checks component source, never Android renderer/device behavior.
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
PREPARED=Path('/home/user/Documents/github/overte-parallel-20261002-220349/evidence/skinning-review/integration-proof/conan-home/p/gifcr2d5c2c169099c/p/include/GifCreator.h')
PREFIX=r'''
#include <cstdio>
#include <stdexcept>
#include <QCoreApplication>
#include <QImage>
#include <QImageReader>
#include <QVector>
#include <QDir>
#include <QFile>
#include <QCryptographicHash>
#include <GifCreator.h>
#include "interface/src/ui/SnapshotCapture.h"
#include "interface/src/ui/SnapshotStorage.h"
#include "tests/device/native/PhoneSnapshotCaptureFiles.h"
static SnapshotCapture cancelDuringWrite;
static bool actualFrame(GifWriter* writer,const uint8_t* bytes,uint32_t width,uint32_t height,uint32_t delay) {
    const bool result=GifWriteFrame(writer,bytes,width,height,delay);
    if(cancelDuringWrite)cancelDuringWrite->cancel();
    return result;
}
#define GifWriteFrame actualFrame
class SnapshotAnimated { public:static bool processFrames(QVector<QImage> frames,QVector<qint64> delays,QString path,SnapshotCapture request); };
'''
SUFFIX=r'''
static void need(bool value){if(!value)throw std::runtime_error("Original real GIF owner contract");}
int main(int argc,char**argv) {
    QCoreApplication app(argc,argv);app.setApplicationName("actual-snapshot-gif-owner");
    const QString mode=argv[1],root=overte::snapshot::storageRoot(),run(32,'a'),plan(32,'b'),prefix="e2e-"+run,capture="actual_gif_worker",path=QDir(root).filePath(prefix+"-"+capture+".gif");
    need(QDir().mkpath(root));auto request=std::make_shared<SnapshotCaptureRequest>(capture);
    QImage image(16,16,QImage::Format_RGBA8888);image.fill(Qt::green);QVector<QImage> frames{image,image};QVector<qint64> delays{4,4};
    if(mode=="failure")frames[1]=QImage(1,1,QImage::Format_RGBA8888);
    if(mode=="cancel")cancelDuringWrite=request;
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    auto& owner=overte::e2e::PhoneSnapshotCaptureFiles::get();need(owner.plan(run,prefix,plan,root));owner.begin(capture);
#endif
    const auto result=SnapshotAnimated::processFrames(frames,delays,path,request);need(result==(mode=="success"));
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    owner.terminal(capture,result ? "complete" : mode=="cancel" ? "cancelled" : "error",result ? path : QString());
    const auto source=owner.snapshot();need(source.value("complete")==true && source.value("rows").toList().size()==1);
    const auto original=source.value("rows").toList().front().toMap();need(original.value("opened")==true && original.value("closed")==true);
    if(result) { QFile actual(path);need(actual.open(QIODevice::ReadOnly));const auto bytes=actual.readAll();actual.close();need(original.value("sha256")==QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())); }
    else need(original.value("nativeRemoved")==true);
    need(owner.retire(run,original.value("id").toString(),QString(32,'c')) && !QFileInfo(path).exists());need(owner.seal(run,plan,QString(32,'d')));
#else
    need(QFileInfo(path).exists()==result);
#endif
    return 0;
}
'''


class SnapshotCaptureGifNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dependency=Path(os.environ.get('OVERTE_TEST_GIFCREATOR_HEADER',str(PREPARED)))
        if not dependency.is_file():raise RuntimeError('Prepared real GifCreator header is required; no mock codec fallback')
        parent=ROOT/'build/snapshot-capture-gif-native';parent.mkdir(parents=True,exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(prefix='cpp-',dir=parent);cls.addClassCleanup(cls.temporary.cleanup);cls.build=Path(cls.temporary.name)
        raw=(ROOT/'interface/src/ui/SnapshotAnimated.cpp').read_text();function=raw[raw.index('bool SnapshotAnimated::processFrames('):]
        cpp=cls.build/'actual.cpp';cpp.write_text(PREFIX+function+SUFFIX)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui'],text=True));cls.binaries={}
        for profile,defines in [('phone',['OVERTE_E2E_FEATURE_TESTS','ANDROID_APP_PHONE_INTERFACE']),('production',[])]:
            binary=cls.build/profile;subprocess.run(['c++','-std=c++17','-fPIC','-I'+str(ROOT),'-I'+str(dependency.parent),
                *['-D'+key for key in defines],str(cpp),'-o',str(binary),*flags],check=True,timeout=30);cls.binaries[profile]=binary
    def case(self,mode,profile='phone'):
        with tempfile.TemporaryDirectory(prefix='original-',dir=self.build) as data:
            result=subprocess.run([str(self.binaries[profile]),mode,'--testScript'],capture_output=True,text=True,timeout=10,env=os.environ|{'XDG_DATA_HOME':data})
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
    def test_actual_real_gif_worker_fd_body_close_and_retirement(self):self.case('success')
    def test_actual_partial_gif_error_and_mid_write_cancel_retire_originals(self):self.case('failure');self.case('cancel')
    def test_production_real_gif_worker_behavior_is_preserved(self):
        for mode in ('success','failure','cancel'):self.case(mode,'production')

if __name__=='__main__':unittest.main()
