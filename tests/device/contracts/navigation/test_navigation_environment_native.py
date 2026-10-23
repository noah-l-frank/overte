"""Whole passive Navigation source + original bounded typed Manager read.

Account/DI and Manager storage are explicit host seams, not native-account or
physical-settings qualification. Actual Qt objects, locks and login helpers run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('navigation_body',ROOT/'tests/device/contracts/snapshot/test_snapshot_context_native.py')
context=importlib.util.module_from_spec(spec);spec.loader.exec_module(context)
SETTING=r'''
#pragma once
#include <QCoreApplication>
#include <QDateTime>
#include <QThread>
#include <QVariantMap>
#include <QHash>
#include <QObject>
#include <QUrl>
#include <QUuid>
#include <QDataStream>
#include <QCryptographicHash>
#include "libraries/shared/src/shared/ReadWriteLockable.h"
namespace Setting {
// Original Manager constructor/writer are deliberately not started by a reader.
// A registered pointer may be inaccessible: the reader must never dereference it.
class Manager : public QObject,public ReadWriteLockable {
public:
    QHash<QString,QVariant> _settings;QHash<QString,void*> _handles;
    MANAGER_BIRTH
    QVariantMap featureNavigationEnvironmentEntries() const;
};
}
'''
ACCOUNT=r'''
#pragma once
#include <QObject>
#include <QUrl>
#include <QVariantMap>
#include <QDateTime>
#include <QCryptographicHash>
class AccountManager : public QObject {
public:
    QUrl url{QStringLiteral("https://selected.invalid/server")};bool mismatch=false;int observations=0,urlReads=0;
    QUrl getAuthURL() {++urlReads;return url;}
    QVariantMap featureAccountObservation() {
        ++observations;
        const auto digest=[](const QByteArray& raw){return QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex());};
        return {{"loggedIn",false},{"principalSha256",digest("")},{"observation",QVariantMap{
            {"accountVersion",1},{"instance",QString(32,'d')},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"credentialGeneration",1},{"credentialActive",true},{"endpointPresent",true},
            {"endpointSha256",mismatch?QString(64,'f'):digest(url.toString(QUrl::FullyEncoded).toUtf8())},
            {"loginPending",false},{"refreshPending",false},{"tokenPresent",false},{"tokenValid",false},
            {"refreshPresent",false},{"transportRejected",false},{"eventSequence",0},{"droppedEvents",0},{"events",QVariantList{}}}}};
    }
};
'''
DI=r'''
#pragma once
#include <QSharedPointer>
#include <type_traits>
#include "AccountManager.h"
#include "SettingManager.h"
class DependencyManager {
public:
    static QSharedPointer<Setting::Manager> manager;static QSharedPointer<AccountManager> account;static int reads;
    template<class T>static bool isSet(){if constexpr(std::is_same<T,Setting::Manager>::value)return !manager.isNull();else return !account.isNull();}
    template<class T>static QSharedPointer<T>get(){++reads;if constexpr(std::is_same<T,Setting::Manager>::value)return manager;else return account;}
};
'''
MAIN=r'''
#include <QGuiApplication>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QSemaphore>
#include <thread>
#include <cstdio>
#include "tests/device/native/NavigationEnvironmentObservation.h"
QSharedPointer<Setting::Manager> DependencyManager::manager;
QSharedPointer<AccountManager> DependencyManager::account;
int DependencyManager::reads=0;
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);const QString mode=QString::fromLocal8Bit(argv[1]);
    qunsetenv("HIFI_METAVERSE_URL");
    auto manager=QSharedPointer<Setting::Manager>::create();auto account=QSharedPointer<AccountManager>::create();
    DependencyManager::manager=manager;DependencyManager::account=account;
    manager->_settings={{"private/selectedMetaverseURL",QUrl("https://selected.invalid/server")},
        {"placesAppPinnedMetaverse",QStringList{"https://pinned.invalid/server"}}};
    const auto before=manager->_settings;
    overte::e2e::NavigationEnvironmentObservation source;
    auto frame=[](bool open=false,bool ready=false){return QJsonObject{{"open",open},{"ready",ready},{"controls",QJsonArray{}},
        {"bridgeId","11111111-1111-4111-8111-111111111111"},{"generation","22222222-2222-4222-8222-222222222222"},
        {"lastCommandSequence",0},{"elapsedMs",100},{"updatedEpochMs",QDateTime::currentMSecsSinceEpoch()}};};
    QVariantMap request{{"schemaVersion",1},{"commandId",QString(32,'a')},{"runId",QString(32,'b')},{"action","feature-navigation-environment"}};
    auto read=[&](const QJsonObject& ui){source.observe(ui,nullptr,nullptr);return source.snapshot(request);};
    if(mode=="disabled")return read(frame()).isEmpty() && manager->featureNavigationEnvironmentEntries().isEmpty() && DependencyManager::reads==0 ? 0:1;
    if(mode=="missing") {
        DependencyManager::manager.clear();if(!read(frame()).isEmpty() || DependencyManager::reads)return 2;
        DependencyManager::manager=manager;DependencyManager::account.clear();return read(frame()).isEmpty() && DependencyManager::reads==0?0:3;
    }
    if(mode=="wrong-thread") {
        QVariantMap value;std::thread worker([&]{value=manager->featureNavigationEnvironmentEntries();source.observe(frame(),nullptr,nullptr);if(!source.snapshot(request).isEmpty())value.insert("foreign",true);});worker.join();
        return value.isEmpty() && DependencyManager::reads==0 && manager->_settings==before?0:4;
    }
    if(mode=="account-thread") {
        QThread worker;worker.start();account->moveToThread(&worker);const auto value=read(frame());
        QMetaObject::invokeMethod(account.data(),[&]{account->moveToThread(app.thread());},Qt::BlockingQueuedConnection);
        worker.quit();worker.wait();return value.isEmpty() && account->observations==0 && account->urlReads==0 && manager->_settings==before?0:24;
    }
    if(mode=="blocked") {
        QSemaphore entered,release;std::thread worker([&]{QWriteLocker lock(&manager->getLock());entered.release();release.acquire();});entered.acquire();
        QElapsedTimer timer;timer.start();const auto value=read(frame());const auto elapsed=timer.elapsed();release.release();worker.join();
        return value.isEmpty() && elapsed>=15 && elapsed<1000 && !read(frame()).isEmpty() && manager->_settings==before?0:5;
    }
    if(mode=="active-handle") {
        // Inaccessible registered handle versus persisted selected URL: neither
        // a cached nor deferred effective value may be guessed from the latter.
        for(const auto& key:QStringList{"private/selectedMetaverseURL","placesAppPinnedMetaverse","placesAppMetaverseToFetch","placesAppMaturityFilter"}) {
            manager->_handles.insert(key,reinterpret_cast<void*>(1));
            if(!read(frame()).isEmpty() || manager->_settings!=before)return 6;
            manager->_handles.clear();
        }
        return !read(frame()).isEmpty()?0:7;
    }
    if(mode=="typed") {
        const auto original=manager->featureNavigationEnvironmentEntries();
        manager->_settings["placesAppPinnedMetaverse"]=QVariantList{QString("https://pinned.invalid/server")};
        const auto changed=manager->featureNavigationEnvironmentEntries();
        if(original.value("otherSettingsSha256")==changed.value("otherSettingsSha256"))return 8;
        manager->_settings["placesAppPinnedMetaverse"]=QVariantList{true};
        if(!manager->featureNavigationEnvironmentEntries().isEmpty())return 9;
        manager->_settings=before;manager->_settings["private/selectedMetaverseURL"]=true;
        return manager->featureNavigationEnvironmentEntries().isEmpty()?0:10;
    }
    if(mode=="contradiction") {
        account->url=QUrl("https://runtime.invalid/server");if(!read(frame()).isEmpty())return 11;
        account->url=QUrl("https://selected.invalid/server");account->mismatch=true;if(!read(frame()).isEmpty())return 12;
        account->mismatch=false;qputenv("HIFI_METAVERSE_URL","https://override.invalid/server");if(!read(frame()).isEmpty())return 13;
        account->url=QUrl("https://override.invalid/server");const auto value=read(frame());
        return value.value("environmentOverride")==true && value.value("effectiveServer")==account->url.toString() && manager->_settings==before?0:14;
    }
    if(mode=="closed-boundary") {
        if(!read(frame(true,false)).isEmpty() || !read(frame(false,true)).isEmpty())return 15;
        auto old=frame();old["updatedEpochMs"]=QDateTime::currentMSecsSinceEpoch()-2000;if(!read(old).isEmpty())return 16;
        auto malformed=frame();malformed["ready"]=0;if(!read(malformed).isEmpty())return 17;
        auto controls=frame();controls["controls"]=QJsonArray{QJsonObject{{"id","foreign"}}};if(!read(controls).isEmpty())return 18;
        QQuickItem retained;source.observe(frame(),nullptr,&retained);if(!source.snapshot(request).isEmpty())return 19;
        return !read(frame()).isEmpty()?0:20;
    }
    const auto closed=read(frame());if(closed.value("navigationEnvironmentVersion")!=2 || closed.value("ui").toMap().value("open")!=false
        || closed.value("settings").toMap().value("instance")!=manager->_featureSnapshotContextInstance || manager->_settings!=before)return 21;
    if(!source.snapshot(request).isEmpty())return 22;
    request["commandId"]=QString(32,'c');const auto opened=read(frame(true,true));if(opened.isEmpty())return 23;
    std::puts(QJsonDocument::fromVariant(QVariantList{closed,opened}).toJson(QJsonDocument::Compact).constData());
}
'''


class NavigationEnvironmentNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stage=tempfile.TemporaryDirectory(prefix='navigation-environment-native-');cls.addClassCleanup(stage.cleanup);stage=Path(stage.name);cls.executable=stage/'check'
        manager=(ROOT/'libraries/shared/src/SettingManager.h').read_text()
        birth=next(line.strip() for line in manager.splitlines() if 'const QString _featureSnapshotContextInstance{' in line)
        (stage/'SettingManager.h').write_text(SETTING.replace('MANAGER_BIRTH',birth))
        (stage/'AccountManager.h').write_text(ACCOUNT);(stage/'DependencyManager.h').write_text(DI)
        (stage/'NetworkingConstants.h').write_text('#pragma once\n#include <QUrl>\nnamespace NetworkingConstants {const QUrl METAVERSE_SERVER_URL_STABLE{"https://default.invalid/server"};}\n')
        source=stage/'actual.cpp';source.write_text('#include "SettingManager.h"\n'
            +context.body((ROOT/'libraries/shared/src/SettingManager.cpp').read_text(),'QVariantMap Setting::Manager::featureNavigationEnvironmentEntries(')+MAIN)
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');library=[]
        if major not in ('5','6'):raise ValueError('Unsupported Qt major')
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
                QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
            library=['-L'+str(prefix/'usr/lib64')]
        environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software');cls.environment=environment
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Quick','Qt'+major+'Qml'],text=True,env=environment))
        subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
            '-I'+str(stage),'-I'+str(ROOT),str(source),'-o',str(cls.executable),*library,*flags],check=True,timeout=60,env=environment)

    def test_actual_closed_open_runtime_typed_settings_and_conservative_unavailable_boundaries(self):
        from adapters.native_navigation_environment import validate,continuation
        for mode in ('original','disabled','missing','wrong-thread','account-thread','blocked','active-handle','typed','contradiction','closed-boundary'):
            with self.subTest(mode=mode):
                raw=subprocess.check_output([str(self.executable),mode,*([] if mode=='disabled' else ['--testScript'])],text=True,timeout=5,env=self.environment)
                if mode=='original':
                    rows=json.loads(raw)
                    for row in rows:
                        validate(row,dict(schemaVersion=1,commandId=row['commandId'],action='feature-navigation-environment',runId=row['runId']),row['processId'],row['capturedEpochMs'])
                    continuation(*rows)


if __name__=='__main__':unittest.main()
