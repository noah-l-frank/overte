#!/usr/bin/env python3
"""Compile the actual passive registry method with real Qt weak ownership.

Resource loading/animation rows are explicit seams. This does not compile the
whole AnimationCache, product, Android or headset implementation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]


def original_body(source, marker):
    start = source.index(marker); opening = source.index('{', start)
    depth = 1; end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}'); end += 1
    return source[start:end]


HARNESS = r'''
#include <QCoreApplication>
#include <QHash>
#include <QReadWriteLock>
#include <QSharedPointer>
#include <QThread>
#include <QUrl>
#include <QVariantMap>
#include <algorithm>
#include <cassert>
#include <functional>
struct Resource:QObject { virtual ~Resource()=default; };
struct Animation:Resource {
    QVariantMap row; std::function<void()> during;
    QVariantMap featureResourceObservation() const { if(during)during(); return row; }
};
struct AnimationCache {
    QHash<QUrl,QMultiHash<size_t,QWeakPointer<Resource>>> _resources;
    QReadWriteLock _resourcesLock;
    QVariantMap featureResourceObservation();
    void insert(const QString& url,const QSharedPointer<Resource>& resource,size_t key=0) {
        _resources[QUrl(url)].insert(key,resource.toWeakRef());
    }
};
SOURCE
QSharedPointer<Animation> item(const QString& id) {
    auto resource=QSharedPointer<Animation>::create();
    resource->row={{"resourceInstance",id},{"urlSha256",QString(64,'a')},
        {"loaded",false},{"failed",false},{"model",QVariant()}};
    return resource;
}
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv); AnimationCache cache;
    const bool admitted=app.arguments().contains("--testScript");
    assert(cache.featureResourceObservation().value("complete").toBool()==admitted);
    if(!admitted)return 0;
    auto a=item(QString(32,'a')),b=item(QString(32,'b'));
    cache.insert("qrc:/a",a); cache.insert("qrc:/a",a,1); cache.insert("qrc:/b",b);
    { auto expired=item(QString(32,'c')); cache.insert("qrc:/expired",expired); }
    const auto packet=cache.featureResourceObservation();
    assert(packet.value("complete").toBool());assert(packet.value("registrySlots").toInt()==4);
    assert(packet.value("expiredSlots").toInt()==1);const auto rows=packet.value("resources").toList();
    assert(rows.size()==2 && rows[0].toMap().value("resourceInstance")==QString(32,'a'));
    assert(rows[0].toMap().value("registrySlots").toInt()==2 && rows[0].toMap().value("model").isNull());
    assert(cache.featureResourceObservation()==packet); // Reads neither load nor retime rows.
    a->during=[&]{cache._resources.clear();};assert(!cache.featureResourceObservation().value("complete").toBool());
    a->during={};cache._resources.clear();cache.insert("qrc:/a",a);
    a->row.remove("resourceInstance");assert(!cache.featureResourceObservation().value("complete").toBool());
    a->row.insert("resourceInstance",QString(32,'a'));
    QThread foreign;b->moveToThread(&foreign);cache.insert("qrc:/b",b);
    assert(!cache.featureResourceObservation().value("complete").toBool());cache._resources.clear();
    auto other=QSharedPointer<Resource>::create();cache.insert("qrc:/other",other);
    assert(!cache.featureResourceObservation().value("complete").toBool());cache._resources.clear();
    for(int i=0;i<1025;++i)cache.insert(QString("qrc:/%1").arg(i),a);
    assert(!cache.featureResourceObservation().value("complete").toBool());cache._resources.clear();
    for(int i=0;i<1025;++i)cache.insert("qrc:/many-slots",a,i);
    assert(!cache.featureResourceObservation().value("complete").toBool());cache._resources.clear();
    QList<QSharedPointer<Animation>> owners;
    for(int i=0;i<257;++i){auto row=item(QString("%1").arg(i,32,16,QChar('0')));owners.append(row);cache.insert(QString("qrc:/%1").arg(i),row);}
    assert(!cache.featureResourceObservation().value("complete").toBool());
    cache._resources.clear();assert(cache.featureResourceObservation().value("complete").toBool());
}
'''


class AnimationInventoryNativeTests(unittest.TestCase):
    def test_original_registry_method_with_real_weak_maps_and_locking(self):
        source = (ROOT / 'libraries/animation/src/AnimationCache.cpp').read_text()
        major = os.environ.get('OVERTE_ANIMATION_TEST_QT', 'Qt5')
        self.assertIn(major, ('Qt5', 'Qt6'))
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', major + 'Core'], text=True))
        if os.environ.get('PKG_CONFIG_SYSROOT_DIR'):
            library = subprocess.check_output(['pkg-config', '--variable=libdir', major + 'Core'], text=True).strip()
            flags = ['-L' + library, '-Wl,-rpath,' + library, *flags]
        with tempfile.TemporaryDirectory(prefix='overte-animation-inventory-') as scratch:
            unit = Path(scratch) / 'test.cpp'; binary = Path(scratch) / 'test'
            unit.write_text(HARNESS.replace('SOURCE', original_body(source,
                'QVariantMap AnimationCache::featureResourceObservation() {')))
            built = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fPIC',
                str(unit), '-o', str(binary), *flags], capture_output=True, text=True, timeout=45)
            self.assertEqual(0, built.returncode, built.stderr[:6000])
            for arguments in ([], ['--testScript']):
                ran = subprocess.run([str(binary), *arguments], capture_output=True, text=True, timeout=10)
                self.assertEqual(0, ran.returncode, ran.stderr[:2000])


if __name__ == '__main__': unittest.main()
