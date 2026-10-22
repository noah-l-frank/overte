// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual Setting::Manager and native cleanup lease. GUI closure/Erase is an
// explicit host seam, separately covered by the original QML ordinary inputs.
#include <QCoreApplication>
#include <QTemporaryDir>
#include <QSettings>
#include <iostream>
#include <QJsonDocument>
#include <QSignalSpy>
#include "libraries/shared/src/SettingManager.h"
#include "tests/device/native/ChatEmptyHistoryLease.h"
class HostSettings : public Setting::Manager { public: using Setting::Manager::terminateThread; };
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir directory;if (!directory.isValid()) { return 1; }
    QCoreApplication::setOrganizationName("Overte-E2E-Host");QCoreApplication::setApplicationName("Chat-history");
    QSettings::setPath(QSettings::NativeFormat,QSettings::UserScope,directory.path());
    auto manager=new HostSettings();
    auto read=[&] { QVariantMap state;manager->withReadLock([&] { state={{"historyPresent",manager->contains("ArmoredChat-Messages")},{"history",manager->value("ArmoredChat-Messages")},
        {"configPresent",manager->contains("ArmoredChat-Config")},{"config",manager->value("ArmoredChat-Config")}}; });return state; };
    const auto restore=[&](const QVariantMap& expected,const QVariantMap& original) { return manager->featureRestoreEmptyChat(expected,original); };
    int status{0};
    for (int type=0;type<5;++type) {
        manager->remove("ArmoredChat-Messages");manager->setValue("ArmoredChat-Config",QVariantMap{{"maximum_messages",200}});
        if (type==1) { manager->setValue("ArmoredChat-Messages",QVariant()); }
        if (type==2) { manager->setValue("ArmoredChat-Messages",QString("")); }
        if (type==3) { manager->setValue("ArmoredChat-Messages",QVariantList()); }
        if (type==4) { manager->setValue("ArmoredChat-Messages",QStringList()); }
        const auto original=read();overte::e2e::ChatEmptyHistoryLease lease;
        const auto query=[&](const QString& operation) { return QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"action","feature-chat-history"},{"operation",operation},{"runId",QString(32,'a')}}; };
        const auto request=[&](const QString& operation,bool closed=true) { return lease.request(query(operation),closed,read,restore); };
        if (!request("capture",false).isEmpty() || request("capture").isEmpty()) { status=2;break; }
        // Explicit synthetic normal-Erase producer: the actual script handler
        // uses this live setting write after clearing its own messageHistory.
        manager->setValue("ArmoredChat-Messages",QVariant());
        if (!request("restore",false).isEmpty()) { status=3;break; }
        const auto expected=read();manager->setValue("ArmoredChat-Config",QVariantMap{{"maximum_messages",201}});
        if (restore(expected,original) || !request("restore").isEmpty()) { status=4;break; }
        manager->setValue("ArmoredChat-Config",original.value("config"));
        QSignalSpy changed(manager,SIGNAL(valueChanged(QString,QVariant))),removed(manager,SIGNAL(keyRemoved(QString)));
        const auto restored=request("restore");
        if (restored.isEmpty() || overte::e2e::ChatEmptyHistoryLease::bytes(read())!=overte::e2e::ChatEmptyHistoryLease::bytes(original)) { status=5;break; }
        const bool same=overte::e2e::ChatEmptyHistoryLease::bytes(expected)==overte::e2e::ChatEmptyHistoryLease::bytes(original);
        if (changed.size()!=(same || type==0?0:1) || removed.size()!=(type==0?1:0)) { status=7;break; }
        for (const auto& args:changed) { if (args.at(0)!="ArmoredChat-Messages") { status=8; } }
        const auto handback=restored.value("source").toMap().value("handbackEpochMs");
        if (request("restore").value("source").toMap().value("handbackEpochMs")!=handback || request("retire").isEmpty()
                || !request("capture").isEmpty() || request("inspect").value("source").toMap().value("scopePresent").toBool()) { status=6;break; }
        std::cout<<QJsonDocument(QJsonObject::fromVariantMap(restored)).toJson(QJsonDocument::Compact).constData()<<'\n';
    }
    manager->terminateThread();
    if (status) { return status; }
    std::cout<<"PASS: actual Setting::Manager empty variant/presence CAS, foreign config refusal, closed UI gate and immutable restore/retire\n";return 0;
}
