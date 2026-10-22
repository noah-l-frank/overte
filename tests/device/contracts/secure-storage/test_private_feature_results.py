#!/usr/bin/env python3
"""Compile the original result writer and verify actual private output modes.

The GPU receipt types are explicit compile-only seams. No GPU/device/application
is run and no alternate result writer is used.
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
HARNESS=r'''
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSaveFile>
#include <QTemporaryDir>
#include <QVariant>
#include <cassert>
#include <sys/stat.h>
#include "tests/device/native/PrivatePreviewFiles.h"
struct GPUReceiptBoundary {QByteArray receiptDigest(const QString&,const QString&,bool){return {};}};
struct GPUContextBoundary {GPUReceiptBoundary* featureWorldRender(){return nullptr;}};
struct AppBoundary:QCoreApplication {using QCoreApplication::QCoreApplication;GPUContextBoundary* getGPUContext(){return nullptr;}};
#undef qApp
#define qApp static_cast<AppBoundary*>(QCoreApplication::instance())
struct TestScriptingInterface {QString _testResultsLocation;void saveObject(QVariant,const QString&);};
SOURCE
int main(int argc,char** argv){
    AppBoundary app(argc,argv);QTemporaryDir directory;assert(directory.isValid());::umask(0);
    const auto root=directory.path();assert(::chmod(QFile::encodeName(root).constData(),0700)==0);
    TestScriptingInterface writer{root};const QVariantMap value{{"original","bounded-owned-observation"}};
    const bool active=app.arguments().contains("--testScript");
    for(const auto name:QStringList{"feature-new-unlisted-observation.json","feature-script-roots.json",
            "feature-animation-inventory.json","feature-create-callbacks.json","feature-chat-peer-position.json",
            "feature-lifecycle-drive.json","normal-feature-observation.json","recorded-preview-observation.json"}){
        writer.saveObject(value,name);const auto path=root+'/'+name;
        if(!active){assert(!QFileInfo::exists(path));continue;}
        struct stat info{};assert(::lstat(QFile::encodeName(path).constData(),&info)==0);
        assert(S_ISREG(info.st_mode) && (info.st_mode&0777)==0600 && info.st_nlink==1);
        QFile input(path);assert(input.open(QIODevice::ReadOnly));assert(QJsonDocument::fromJson(input.readAll()).toVariant().toMap()==value);
    }
    for(const auto& name:QStringList{"feature-Mixed.json","feature-.json","feature-test.txt","feature-a..json","feature-a/../outside.json"}){
        writer.saveObject(value,name);assert(!QFileInfo::exists(root+'/'+name));
    }
    QFile target(root+"/untouched.json");assert(target.open(QIODevice::WriteOnly));assert(target.write("original target")==15);target.close();
    const auto alias=root+"/feature-linked-observation.json";assert(QFile::link(target.fileName(),alias));
    writer.saveObject(value,"feature-linked-observation.json");assert(QFileInfo(alias).isSymLink());
    assert(target.open(QIODevice::ReadOnly));assert(target.readAll()=="original target");target.close();
    writer.saveObject(value,"ordinary-metrics.json");assert(QFileInfo::exists(root+"/ordinary-metrics.json"));
}
'''


class PrivateFeatureResultTests(unittest.TestCase):
    def test_original_writer_protects_future_packets_and_refuses_invalid_or_linked_names(self):
        source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        start=source.index('void TestScriptingInterface::saveObject(');end=source.index('\n}\n',start)+3
        major=os.environ.get('OVERTE_PRIVATE_RESULT_QT','Qt5');self.assertIn(major,('Qt5','Qt6'))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',major+'Core'],text=True))
        if os.environ.get('PKG_CONFIG_SYSROOT_DIR'):
            library=subprocess.check_output(['pkg-config','--variable=libdir',major+'Core'],text=True).strip()
            flags=['-L'+library,'-Wl,-rpath,'+library,*flags]
        with tempfile.TemporaryDirectory(prefix='overte-private-feature-writer-') as directory:
            unit=Path(directory)/'test.cpp';binary=Path(directory)/'test'
            unit.write_text(HARNESS.replace('SOURCE',source[start:end]))
            built=subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),
                str(unit),'-o',str(binary),*flags],capture_output=True,text=True,timeout=45)
            self.assertEqual(0,built.returncode,built.stderr[:6000])
            for arguments in ([],['--testScript']):
                ran=subprocess.run([str(binary),*arguments],capture_output=True,text=True,timeout=10)
                self.assertEqual(0,ran.returncode,ran.stderr[:3000])


if __name__=='__main__':unittest.main()
