// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSWebClosureTrace.h"
#include "IOSTabletWebTrace.h"
namespace overte::ios::tablet_web_closures {
using Function=std::function<QVariantMap(const QVariantMap&)>;
struct Provider final:Function { using Function::Function; };
inline const char* providerProperty() { return "_overteE2EIOSTabletWebClosuresProviderV1"; }
inline bool command(const QVariantMap& value) {
    if (QJsonObject::fromVariantMap(value).value("action")!=QJsonValue("feature-ios-tablet-web-closures")) { return false; }
    auto original=value;original["action"]="feature-ios-tablet-web";return tablet_web_trace::command(original);
}
// This actual source owns a separate passive counter history. Its objects are
// only metadata; no context retains a WK view, event, callback or product image.
inline feature_closures::State& state() { static auto* actual=new feature_closures::State;return *actual; }
inline feature_closures::ContextPointer context(quint64 handle,quint64 creation,quint64 grant,quint64 page,
        const QString& identity,const QString& source,const QVariantMap& stamp) {
    if (!world_web_trace::enabled() || !world_web_trace::mainThread() || !grant || stamp.isEmpty()) { return {}; }
    const auto root=tablet_web_trace::rootFor({{"surface","tablet"},{"source",stamp}});
    if (root.isEmpty()) { return {}; }
    const auto json=QJsonObject::fromVariantMap(stamp);const QUrl url(source,QUrl::StrictMode);
    const bool inlineSource=!json.value("carrier").isNull();
    if (!url.isValid() || url.toString(QUrl::FullyEncoded)!=source || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment()) { return {}; }
    if (inlineSource) {
        if (!QRegularExpression("\\Ahttp://[0-9a-f]{32}\\.overte-inline\\.invalid/index\\.html\\z").match(source).hasMatch()) { return {}; }
    } else {
        const auto prefix=root+"tickets/";
        if (!source.startsWith(prefix) || !QRegularExpression("\\A[0-9a-f]{32}/(?:index|reference)\\.html\\z").match(source.mid(prefix.size())).hasMatch()) { return {}; }
    }
    auto& data=state();std::lock_guard<std::mutex> guard(data.mutex);const auto now=QDateTime::currentMSecsSinceEpoch();
    if (!handle || handle>feature_closures::LIMIT || creation>feature_closures::LIMIT || grant>feature_closures::LIMIT
            || page>feature_closures::LIMIT || identity.isEmpty() || now<=0 || now<data.epoch) { data.complete=false;return {}; }
    QVariantMap descriptor{{"handle",static_cast<qulonglong>(handle)},{"creation",static_cast<qulonglong>(creation)},
        {"grant",static_cast<qulonglong>(grant)},{"page",static_cast<qulonglong>(page)},{"surface","tablet"},
        {"identitySha256",QString::fromLatin1(QCryptographicHash::hash(identity.toUtf8(),QCryptographicHash::Sha256).toHex())},
        {"sourceUrl",source},{"source",stamp}};
    const auto key=QString::fromUtf8(QJsonDocument(QJsonObject::fromVariantMap(descriptor)).toJson(QJsonDocument::Compact));
    const auto found=data.identities.find(key);
    if (found!=data.identities.end()) { return std::make_shared<feature_closures::Context>(feature_closures::Context{found->second,&data}); }
    if (data.rows.size()>=feature_closures::MAX_CONTEXTS || !data.next || data.next>feature_closures::LIMIT) { data.complete=false;return {}; }
    const auto id=data.next++;data.epoch=now;feature_closures::Row row;row.descriptor=descriptor;row.createdEpochMs=row.updatedEpochMs=now;
    data.rows.emplace(id,std::move(row));data.identities.emplace(key,id);
    return std::make_shared<feature_closures::Context>(feature_closures::Context{id,&data});
}
inline QVariantMap observe(const QVariantMap& request) {
    if (!world_web_trace::enabled() || !world_web_trace::mainThread() || !command(request)) { return {}; }
    auto& data=state();std::lock_guard<std::mutex> guard(data.mutex);const auto now=QDateTime::currentMSecsSinceEpoch();
    if (now<=0 || now<data.epoch || data.sequence>=feature_closures::LIMIT) { data.complete=false;return {}; }
    data.epoch=now;QVariantList rows;const auto fixture=request.value("fixtureUrl").toString();
    for (const auto& [id,row]:data.rows) {
        if (row.descriptor.value("source").toMap().value("fixtureUrl")!=fixture) { continue; }
        QVariantMap callbacks,resources;
        for (std::size_t i=0;i<feature_closures::NAMES.size();++i) {
            const auto& counter=row.counters[i];auto& collection=i<feature_closures::CALLBACK_KINDS ? callbacks : resources;
            collection.insert(feature_closures::NAMES[i],QVariantMap{{"created",static_cast<qulonglong>(counter.created)},
                {"retired",static_cast<qulonglong>(counter.retired)},{"pending",static_cast<qulonglong>(counter.created-counter.retired)}});
        }
        rows.push_back(QVariantMap{{"id",static_cast<qulonglong>(id)},{"descriptor",row.descriptor},{"createdEpochMs",row.createdEpochMs},
            {"updatedEpochMs",row.updatedEpochMs},{"callbacks",callbacks},{"resources",resources}});
    }
    QVariantMap result{{"iosTabletWebClosuresVersion",1},{"commandId",request.value("commandId")},{"runId",request.value("runId")},
        {"fixtureUrl",fixture},{"instance",data.instance},{"sequence",static_cast<qulonglong>(++data.sequence)},
        {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",now},{"complete",data.complete},{"contexts",rows}};
    if (QJsonDocument(QJsonObject::fromVariantMap(result)).toJson(QJsonDocument::Compact).size()>1048576) { data.complete=false;return {}; }
    return result;
}
} // namespace overte::ios::tablet_web_closures
Q_DECLARE_METATYPE(overte::ios::tablet_web_closures::Provider)
#endif
