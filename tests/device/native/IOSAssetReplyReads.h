// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NativeReadBracket.h"
#include "PrivateAssetFiles.h"
#include <IOSAssetReplyTrace.h>
#include <AssetClient.h>
#include <MappingRequest.h>
#include <QPointer>
#include <QRegularExpression>

namespace overte::e2e {
// Independent read requests only. This never uploads, changes a mapping,
// clears a cache, starts a server/oven or claims a model consumed these bytes.
class IOSAssetReplyReads {
public:
    static bool command(const QVariantMap& value) {
        const auto json=QJsonObject::fromVariantMap(value);const auto operation=value.value("operation").toString();
        QStringList fields{"schemaVersion","commandId","action","runId","ticket","ownerToken","resource","namespace","operation"};
        if (QStringList{"mapping","info","raw-server"}.contains(operation)) {fields<<"sourceJob"<<"relativePath";}
        if (operation=="observe" || operation=="retire") {fields<<"jobId";}fields.sort();
        const auto token=[](const QJsonValue& item,const QString& pattern) {
            return item.isString() && QRegularExpression("\\A"+pattern+"\\z").match(item.toString()).hasMatch();
        };
        if (!IOSAssetReplyTrace::enabled() || value.keys()!=fields || json.value("schemaVersion")!=QJsonValue(1)
                || json.value("action")!=QJsonValue("feature-ios-assets-replies") || !token(json.value("commandId"),"ios-[a-f0-9]{32}")
                || !token(json.value("runId"),"[a-f0-9]{32}") || !token(json.value("ticket"),"[a-f0-9]{32}")
                || !token(json.value("ownerToken"),"[a-f0-9]{64}") || !json.value("resource").isString()
                || PrivateAssetFiles::names(json.value("resource").toString()).isEmpty()
                || !json.value("namespace").isString() || !QStringList{"original","renamed"}.contains(json.value("namespace").toString())
                || !json.value("operation").isString()
                || !QStringList{"inventory","mapping","info","raw-server","observe","retire"}.contains(operation)) {return false;}
        if (fields.contains("sourceJob") && (!token(json.value("sourceJob"),"ios-[a-f0-9]{32}") || !json.value("relativePath").isString()
                || !PrivateAssetFiles::names(json.value("resource").toString()).contains(json.value("relativePath").toString()))) {return false;}
        if (fields.contains("jobId") && !token(json.value("jobId"),"ios-[a-f0-9]{32}")) {return false;}
        return QJsonDocument(json).toJson(QJsonDocument::Compact).size()<=8192;
    }
    QVariantMap read(const QVariantMap& query) {
        if (!command(query) || !QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
                || !DependencyManager::isSet<AssetClient>()) {return {};}
        const auto request=query.value("commandId").toString(),run=query.value("runId").toString();
        if (_commands.contains(request)) {return _commands.value(request)==query ? _results.value(request) : QVariantMap{};}
        if (_commands.size()>=4096) {return {};}_commands.insert(request,query);
        const auto result=_bracket.read("iosAssetsRepliesVersion","native-main-assets-replies",request,run,[&]() -> QVariantMap {
            const auto operation=query.value("operation").toString();const auto client=DependencyManager::get<AssetClient>();
            if (!client || !client->thread() || !client->thread()->isRunning()) {return {};}
            auto& trace=IOSAssetReplyTrace::instance();QString job=query.value("jobId").toString();
            if (operation=="observe" || operation=="retire") {
                const auto previous=trace.read(job);if (!owns(previous,query)) {return {};}
                if (operation=="retire" && previous.value("job").toMap().value("alive").toBool()) {
                    if (!trace.retireIssued(job)) {return {};}
                    if (!QMetaObject::invokeMethod(client.data(),[job] {
                        auto object=IOSAssetReplyTrace::instance().live(job);if (object) {object->deleteLater();}
                    },Qt::QueuedConnection)) {trace.retiredQueueFailed(job);return {};}
                }
            } else {
                QJsonObject inputs{{"path",""},{"hash",""},{"sourceJob",query.value("sourceJob").toString()},{"size",""}};
                if (operation!="inventory") {
                    const auto parent=trace.read(query.value("sourceJob").toString());if (!owns(parent,query) || !drained(parent)) {return {};}
                    const auto parentJob=parent.value("job").toMap();const auto original=QJsonObject::fromVariantMap(parentJob.value("result").toMap());
                    const auto root=(query.value("namespace")=="original" ? "/e2e-" : "/renamed-")+run+'/';
                    const auto path=root+query.value("relativePath").toString();inputs["path"]=path;
                    if (operation=="mapping" || operation=="info") {
                        if (parentJob.value("request").toMap().value("operation")!="inventory" || original.value("error")!=QJsonValue(0)
                                || binding(parent,"mapping-reply").isEmpty()) {return {};}
                        QString hash;
                        for (const auto& item:original.value("mappings").toArray()) {
                            const auto row=item.toObject();if (row.value("path")==QJsonValue(path)) {if (!hash.isEmpty()) {return {};}hash=row.value("hash").toString();}
                        }
                        if (operation=="info" && !QRegularExpression("\\A[a-f0-9]{64}\\z").match(hash).hasMatch()) {return {};}
                        inputs["hash"]=hash;
                    } else {
                        if (parentJob.value("request").toMap().value("operation")!="info" || original.value("responseReceived")!=QJsonValue(true)
                                || original.value("serverError")!=QJsonValue(0) || binding(parent,"info-reply").isEmpty()
                                || parentJob.value("inputs").toMap().value("path")!=path
                                || original.value("hash").toString()!=parentJob.value("inputs").toMap().value("hash").toString()) {return {};}
                        bool okay=false;const auto size=original.value("size").toString().toLongLong(&okay);
                        if (!okay || size<=0 || size>32768 || !QRegularExpression("\\A[a-f0-9]{64}\\z").match(original.value("hash").toString()).hasMatch()) {return {};}
                        inputs["hash"]=original.value("hash");inputs["size"]=original.value("size");
                    }
                }
                const auto control=std::make_shared<Control>();control->kind=operation;QObject* object=nullptr;
                if (operation=="inventory") {object=client->createGetAllMappingsRequest();}
                else if (operation=="mapping") {object=client->createGetMappingRequest(inputs.value("path").toString());}
                else {object=new QObject();object->moveToThread(client->thread());}
                if (!object) {return {};}control->object=object;
                if (!trace.add(object,query,inputs,control)) {object->deleteLater();return {};}
                job=request;
                QObject::connect(object,&QObject::destroyed,client.data(),[control,client,request] {
                    // Actual cancellation happens on the original worker. The
                    // client callback closure and queued body keep control
                    // alive until their real captures have been released.
                    if (control->message) {
                        if (control->kind=="info") {client->cancelGetAssetInfoRequest(control->message);}
                        if (control->kind=="raw-server") {client->cancelGetAssetRequest(control->message);}
                    }
                    IOSAssetReplyTrace::instance().destroyed(request);control->object.clear();
                },Qt::DirectConnection);
                if (operation=="inventory") {
                    auto actual=static_cast<GetAllMappingsRequest*>(object);
                    QObject::connect(actual,&GetAllMappingsRequest::finished,actual,[control](GetAllMappingsRequest* request) {
                        const IOSAssetReplyTrace::Body body(request,"reader");QJsonArray rows;
                        const auto original=request->getMappings();
                        if (original.size()<=256) {
                            for (const auto& row:original) {rows.append(QJsonObject{{"path",row.first},{"hash",row.second.hash},
                                {"status",static_cast<int>(row.second.status)},{"bakingErrors",row.second.bakingErrors}});}
                        }
                        IOSAssetReplyTrace::instance().result(request,{{"error",static_cast<int>(request->getError())},
                            {"complete",original.size()<=256},{"mappings",rows}});request->deleteLater();
                    });
                } else if (operation=="mapping") {
                    auto actual=static_cast<GetMappingRequest*>(object);
                    QObject::connect(actual,&GetMappingRequest::finished,actual,[control](GetMappingRequest* request) {
                        const IOSAssetReplyTrace::Body body(request,"reader");
                        IOSAssetReplyTrace::instance().result(request,{{"error",static_cast<int>(request->getError())},{"hash",request->getHash()},
                            {"redirected",request->wasRedirected()},{"redirectedPath",request->getRedirectedPath()}});request->deleteLater();
                    });
                }
                if (!QMetaObject::invokeMethod(object,[control,client,inputs] {
                    const auto actual=control->object.data();if (!actual) {return;}
                    if (control->kind=="inventory") {static_cast<GetAllMappingsRequest*>(actual)->start();return;}
                    if (control->kind=="mapping") {static_cast<GetMappingRequest*>(actual)->start();return;}
                    const IOSAssetReplyTrace::Scope start(actual);
                    if (control->kind=="info") {
                        control->message=client->getAssetInfo(inputs.value("hash").toString(),[control](bool received,AssetUtils::AssetServerError error,AssetInfo info) {
                            const auto object=control->object.data();if (!object) {return;}
                            const IOSAssetReplyTrace::Body body(object,"network",{{"responseReceived",received},{"serverError",error}});control->message=INVALID_MESSAGE_ID;
                            IOSAssetReplyTrace::instance().result(object,{{"responseReceived",received},{"serverError",error},{"hash",info.hash},{"size",QString::number(info.size)}});object->deleteLater();
                        });
                    } else {
                        const auto size=inputs.value("size").toString().toLongLong();
                        control->message=client->getAsset(inputs.value("hash").toString(),0,size,
                            [control](bool received,AssetUtils::AssetServerError error,const QByteArray& data) {
                                const auto object=control->object.data();if (!object) {return;}
                                const IOSAssetReplyTrace::Body body(object,"network",{{"responseReceived",received},{"serverError",error}});control->message=INVALID_MESSAGE_ID;
                                IOSAssetReplyTrace::instance().result(object,{{"responseReceived",received},{"serverError",error},{"body",IOSAssetReplyTrace::bytes(data)}});object->deleteLater();
                            },[](qint64,qint64) {});
                    }
                },Qt::QueuedConnection)) {trace.retiredQueueFailed(job);object->deleteLater();}
            }
            return trace.read(job);
        });
        _results.insert(request,result);return result;
    }
private:
    struct Control {QPointer<QObject> object;QString kind;MessageID message {INVALID_MESSAGE_ID};};
    static bool owns(const QVariantMap& trace,const QVariantMap& query) {
        const auto original=trace.value("job").toMap().value("request").toMap();
        for (const auto& key:QStringList{"runId","ticket","ownerToken","resource","namespace"}) {if (original.value(key)!=query.value(key)) {return false;}}
        return !original.isEmpty();
    }
    static bool drained(const QVariantMap& trace) {
        const auto job=trace.value("job").toMap();
        for (const auto& value:job.value("messages").toList()) {if (value.toMap().value("alive")!=QVariant(false)) {return false;}}
        return trace.value("complete")==QVariant(true) && job.value("alive")==QVariant(false)
            && job.value("tokenAlive")==QVariant(false) && job.value("pendingBodies").toInt()==0 && !job.value("result").toMap().isEmpty();
    }
    static QVariantMap binding(const QVariantMap& trace,const QString& replyKind) {
        QVariantMap sent,reply;
        for (const auto& item:trace.value("job").toMap().value("events").toList()) {
            const auto event=item.toMap();if (event.value("kind")=="sent") {if (!sent.isEmpty()) {return {};}sent=event.value("details").toMap();}
            if (event.value("kind")==replyKind) {if (!reply.isEmpty()) {return {};}reply=event.value("details").toMap();}
        }
        if (sent.isEmpty() || reply.isEmpty() || reply.value("sameTarget")!=QVariant(true) || reply.value("serverError")!=QVariant(0)
                || reply.value("sender")!=sent.value("server") || reply.value("serverInstance")!=sent.value("serverInstance")
                || reply.value("messageId")!=sent.value("messageId") || reply.value("messageComplete")!=QVariant(true)
                || reply.value("messageFailed")!=QVariant(false)) {return {};}
        if (replyKind=="info-reply" && reply.value("messageBytes")!=QVariant("45")) {return {};}
        if (QUuid(sent.value("server").toString()).isNull() || QUuid(sent.value("domainId").toString()).isNull()) {return {};}
        if (replyKind=="info-reply" && (reply.value("hash")!=sent.value("inputs").toMap().value("hash")
                || reply.value("hash")!=trace.value("job").toMap().value("result").toMap().value("hash")
                || reply.value("size")!=trace.value("job").toMap().value("result").toMap().value("size"))) {return {};}
        if (replyKind=="mapping-reply" && reply.value("payload").toMap().value("retained")!=QVariant(true)) {return {};}
        return sent;
    }
    NativeReadBracket _bracket;QMap<QString,QVariantMap> _commands,_results;
};
} // namespace overte::e2e
#endif
