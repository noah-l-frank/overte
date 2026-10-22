// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QCoreApplication>
#include <QTemporaryDir>
#include <QSignalSpy>
#include <QSettings>
#include <QThread>
#include <iostream>
#include "libraries/shared/src/SettingManager.h"
#include "HostSettingHandle.h"
#include "tests/device/native/PhoneSnapshotSettingsLease.h"
#include "tests/device/native/PhoneSnapshotReviewObservation.h"
Q_LOGGING_CATEGORY(settings_handle,"settings.handle")
Q_LOGGING_CATEGORY(settings_interface,"settings.interface")
class HostSettings : public Setting::Manager { public: using Setting::Manager::terminateThread; };
QSharedPointer<HostSettings> originalManager;
// Explicit bootstrap/dependency seam, not a substitute settings implementation.
struct HostDependency {
    template<class T> static bool isSet() { return !originalManager.isNull(); }
    template<class T> static QSharedPointer<T> get() { return originalManager; }
};
#define DependencyManager HostDependency
#include "OriginalSettingInterface.inc"
class Snapshot : public QObject {
public:
    QVariantMap featureSnapshotSettings(const QVariantMap& command,bool closed);
    QVariantMap featureSnapshotObservation() { return {}; } // Explicit GUI/VM source seam, never a success source.
    Setting::Handle<QString> _snapshotFormat{"snapshotFormat"};
    QHash<QString,std::shared_ptr<overte::e2e::PhoneSnapshotSettingsLease>> _featureSnapshotSettingsScopes;
};
#include "OriginalSnapshotSettings.inc"
#undef DependencyManager
// Compile the original Test gateway too. Its surrounding UI/lifecycle objects
// are declarations only; this host check does not execute a native QML closure.
class OffscreenUi { public: QQuickItem* getRootItem() { return nullptr; } };
struct GatewayLifecycle { QVariantMap snapshot() { return {}; } };
struct GatewayDependency {
    template<class T> static bool isSet() { return false; }
    template<class T> static QSharedPointer<T> get() { return {}; }
};
class TestScriptingInterface : public QObject {
public:
    QVariantMap phoneSnapshotSettings(const QVariantMap& command);
    QString _testResultsLocation;std::shared_ptr<GatewayLifecycle> _featureLifecycle;
};
#define DependencyManager GatewayDependency
#include "OriginalSnapshotSettingsGateway.inc"
#undef DependencyManager
using Lease=overte::e2e::PhoneSnapshotSettingsLease;
#define CHECK(condition) do { if (!(condition)) { std::cerr<<"FAIL line "<<__LINE__<<'\n';status=__LINE__;goto finished; } } while (false)
QVariantMap query(const QString& run,const QString& op) {
    return {{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
        {"action","phone-snapshot-settings"},{"runId",run},{"operation",op}};
}
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir directory;if (!directory.isValid()) { return 1; }
    QCoreApplication::setOrganizationName("Overte-E2E-Host");QCoreApplication::setApplicationName("Snapshot-settings");
    QSettings::setPath(QSettings::NativeFormat,QSettings::UserScope,directory.path());
    originalManager.reset(new HostSettings());auto manager=originalManager;int status=0;
    manager->setValue("unrelated",QVariantList{1,QString("preserve")});
    for (int type=0;type<4;++type) {
        manager->remove("snapshotFormat");
        if (type==1) { manager->setValue("snapshotFormat",QVariant()); }
        if (type==2) { manager->setValue("snapshotFormat",QString("")); }
        if (type==3) { manager->setValue("snapshotFormat",QString("jpg")); }
        Snapshot snapshot;const QString run=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        auto capture=query(run,"capture"),malformed=capture;malformed.insert("desired",true);
        CHECK(snapshot.featureSnapshotSettings(malformed,true).isEmpty() && snapshot._featureSnapshotSettingsScopes.isEmpty());
        CHECK(snapshot.featureSnapshotSettings(capture,false).isEmpty() && snapshot._featureSnapshotSettingsScopes.isEmpty());
        const auto initial=snapshot.featureSnapshotSettings(capture,true);CHECK(!initial.isEmpty());
        const auto original=initial.value("source").toMap().value("current").toMap();CHECK(Lease::valid(original));
        // Actual typed native cache and independent raw settings now change.
        snapshot._snapshotFormat.set("png");manager->setValue("alsoTakeAnimatedSnapshot",true);
        manager->setValue("previousStillSnapPath",QString("controlled-original"));
        const auto changed=snapshot.featureSnapshotSettings(query(run,"observe"),false);
        auto restore=query(run,"restore");restore.insert("restoreId",QString(32,'c'));
        restore.insert("expectedSha256",changed.value("source").toMap().value("currentSha256"));
        CHECK(snapshot.featureSnapshotSettings(restore,false).isEmpty());
        auto wrong=restore;wrong.insert("expectedSha256",QString(64,'0'));CHECK(snapshot.featureSnapshotSettings(wrong,true).isEmpty());
        auto expected=manager->featureSnapshotEntries();auto desired=original.value("entries").toMap();
        auto foreign=desired;foreign.insert("unrelated",QVariantMap{{"present",false},{"value",QVariant()}});
        CHECK(!manager->featureRestoreSnapshotEntries(expected,foreign));
        // Counterexample: a raw-only implementation leaves the original native
        // cache changed; it cannot count as complete cleanup.
        CHECK(manager->featureRestoreSnapshotEntries(expected,desired));
        CHECK(snapshot._snapshotFormat.get()=="png");
        CHECK(manager->featureRestoreSnapshotEntries(manager->featureSnapshotEntries(),expected));
        QSignalSpy removed(manager.data(),SIGNAL(keyRemoved(QString)));
        const auto restored=snapshot.featureSnapshotSettings(restore,true);CHECK(!restored.isEmpty());
        CHECK(Lease::same(restored.value("source").toMap().value("current"),original));
        const auto handback=restored.value("source").toMap().value("handbackEpochMs");
        CHECK(snapshot.featureSnapshotSettings(restore,true).value("source").toMap().value("handbackEpochMs")==handback);
        wrong=restore;wrong.insert("restoreId",QString(32,'d'));CHECK(snapshot.featureSnapshotSettings(wrong,true).isEmpty());
        CHECK(!snapshot.featureSnapshotSettings(query(run,"retire"),true).isEmpty());
        CHECK(snapshot.featureSnapshotSettings(capture,true).isEmpty());
        CHECK(manager->value("unrelated")==QVariant(QVariantList{1,QString("preserve")}));
        CHECK(manager->featureSnapshotEntries().keys()==overte::e2e::snapshotSettingsKeys());
    }
    {
        // Lost partial response: first callback really restores raw keys then
        // fails. Resume must accept precisely that retained original transition.
        Snapshot snapshot;const QString run(32,'b');
        const auto first=snapshot.featureSnapshotSettings(query(run,"capture"),true);CHECK(!first.isEmpty());
        snapshot._snapshotFormat.set("png");manager->setValue("alsoTakeAnimatedSnapshot",false);
        auto read=[&] { return QVariantMap{{"format",QVariantMap{{"set",snapshot._snapshotFormat.isSet()},{"value",snapshot._snapshotFormat.get()}}},
            {"entries",manager->featureSnapshotEntries()}}; };
        auto restore=query(run,"restore");restore.insert("restoreId",QString(32,'e'));restore.insert("expectedSha256",Lease::Values::digest(read()));
        const auto owner=snapshot._featureSnapshotSettingsScopes.value(run);
        CHECK(owner->request(restore,true,read,[&](const QVariantMap& expected,const QVariantMap& original) {
            manager->featureRestoreSnapshotEntries(expected.value("entries").toMap(),original.value("entries").toMap());return false;
        }).isEmpty());
        auto wrong=restore;wrong.insert("restoreId",QString(32,'f'));CHECK(snapshot.featureSnapshotSettings(wrong,true).isEmpty());
        CHECK(!snapshot.featureSnapshotSettings(restore,true).isEmpty());
        CHECK(!snapshot.featureSnapshotSettings(query(run,"retire"),true).isEmpty());
    }
finished:
    manager->terminateThread();
    if (status) { return 1; }
    std::cout<<"PASS: actual typed raw/cache restoration, ignored cache counterexample, original presence/type, partial CAS resume and closed UI/foreign key refusal\n";
    return 0;
}
