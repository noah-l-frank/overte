// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QPointer>
#include <QSet>
#include <QThread>
#include <QVariantMap>
#include <QCryptographicHash>

namespace overte::e2e {
inline bool assetsReadCommand(const QVariantMap& command,bool download=false,bool resolve=false) {
    const auto json=QJsonObject::fromVariantMap(command);
    QStringList keys{"schemaVersion","commandId","action","runId"};if (download) { keys.append("hash"); }if (resolve) { keys.append("path"); }keys.sort();
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z"),hash("\\A[0-9a-f]{64}\\z");
    return !(download && resolve) && QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread()
        && QCoreApplication::arguments().contains("--testScript") && command.keys()==keys
        && json.value("schemaVersion").isDouble() && json.value("schemaVersion").toDouble()==1
        && json.value("commandId").isString() && nonce.match(command.value("commandId").toString()).hasMatch()
        && command.value("commandId").toString()!=QString(32,'0')
        && json.value("runId").isString() && nonce.match(command.value("runId").toString()).hasMatch()
        && command.value("runId").toString()!=QString(32,'0')
        && command.value("action").toString()==(download ? "phone-assets-download" : resolve ? "phone-assets-resolve" : "phone-assets-observe")
        && (!download || (json.value("hash").isString() && hash.match(command.value("hash").toString()).hasMatch()))
        && (!resolve || (json.value("path").isString() && QRegularExpression("\\A/(?:e2e-|renamed-)"+command.value("runId").toString()+
            "/(?:main\\.gltf|main\\.obj|stand\\.fbx|mesh/triangle\\.bin|textures/checker\\.png|materials/palette\\.mtl)\\z").match(command.value("path").toString()).hasMatch()));
}
inline bool assetsPath(const QString& path) {
    if (!path.startsWith('/') || path.size()<2 || path.size()>1024 || path.endsWith('/') || path.contains('\\')) { return false; }
    for (auto character:path) { if (character.unicode()<32 || character.unicode()==127) { return false; } }
    for (const auto& part:path.mid(1).split('/')) { if (part.isEmpty() || part=="." || part=="..") { return false; } }
    return true;
}
// Takes the real GetAllMappingsRequest result, including hidden bake mappings.
// No desired paths, expected hashes or editor state enter this reducer.
template<class Mappings> QVariantMap assetsMappingsOriginal(const Mappings& mappings,bool canWrite,const QString& domain,const QString& session,const QString& server) {
    if (mappings.size()>4096 || domain.isEmpty() || session.isEmpty() || server.isEmpty()) { return {}; }
    QVariantList rows;QString previous;
    const QRegularExpression digest("\\A[0-9a-f]{64}\\z");
    for (const auto& pair:mappings) {
        const auto& path=pair.first;const auto& value=pair.second;const auto status=int(value.status);
        if (!assetsPath(path) || (!previous.isEmpty() && path<=previous) || !digest.match(value.hash).hasMatch()
                || status<0 || status>5 || value.bakingErrors.size()>4096) { return {}; }
        rows.append(QVariantMap{{"path",path},{"hash",value.hash},{"bakeStatus",status},{"bakeError",value.bakingErrors}});previous=path;
    }
    return {{"phoneAssetsObservationVersion",2},{"domainId",domain},{"sessionId",session},{"assetServerId",server},{"canWrite",canWrite},
        {"complete",true},{"mappings",rows}};
}
inline QVariantMap assetsDownloadOriginal(const QString& hash,const QByteArray& data,bool cached,const QString& domain,const QString& session,const QString& server) {
    if (domain.isEmpty() || session.isEmpty() || server.isEmpty() || data.isEmpty() || data.size()>1024*1024 || QString::fromLatin1(QCryptographicHash::hash(data,QCryptographicHash::Sha256).toHex())!=hash) { return {}; }
    return {{"phoneAssetsDownloadVersion",2},{"domainId",domain},{"sessionId",session},{"assetServerId",server},{"hash",hash},{"bytes",data.size()},{"base64",QString::fromLatin1(data.toBase64())},{"loadedFromCache",cached}};
}
inline QVariantMap assetsResolveOriginal(const QString& path,const QString& hash,bool redirected,const QString& target,
        const QString& domain,const QString& session,const QString& server) {
    if (!assetsPath(path) || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(hash).hasMatch()
            || (redirected ? !assetsPath(target) : !target.isEmpty()) || domain.isEmpty() || session.isEmpty() || server.isEmpty()) { return {}; }
    return {{"phoneAssetsResolveVersion",1},{"domainId",domain},{"sessionId",session},{"assetServerId",server},
        {"requestedPath",path},{"hash",hash},{"redirected",redirected},{"redirectedPath",target}};
}
// One bounded, original read request. Completion does not become observable
// until the actual QObject has been destroyed; a new command cannot replace an
// unconsumed read or a still-live request. Repeated polling does not retime it.
class PhoneAssetsReadJob {
public:
    bool canBegin(const QVariantMap& command) const { return gui() && !_started && _deliveredIds.size()<4096 && !_deliveredIds.contains(command.value("commandId").toString()); }
    bool same(const QVariantMap& command) const { return _started && _command==command; }
    QVariantMap context() const { return _context; }
    void reject() { if (gui()) { _rejected=true;_source.clear();abort(); } }
    bool begin(const QVariantMap& command,QObject* actual,QObject* cancellation,const QString& instance,quint64 sequence,const QVariantMap& context) {
        if (!canBegin(command) || !actual || !cancellation || cancellation->thread()!=QThread::currentThread() || instance.isEmpty() || !sequence) { return false; }
        _command=command;_context=context;_rejected=false;_request=actual;_cancellation=cancellation;_instance=instance;_sequence=sequence;_requested=QDateTime::currentMSecsSinceEpoch();
        _captured=0;_source.clear();_started=true;_finished=_destroyed=false;return true;
    }
    void finish(QObject* actual,const QVariantMap& original,qint64 capturedEpochMs) {
        if (!gui() || !_started || _finished || _request!=actual) { return; }
        _captured=capturedEpochMs;_source=_rejected ? QVariantMap() : original;_finished=true;
        // The owner uses deleteLater on this exact request after copying data.
    }
    void abort() { if (gui() && _cancellation) { delete _cancellation.data(); } }
    void destroyed(QObject* actual) {
        if (gui() && _started && _request==actual) {
            _destroyed=true;
            if (!_finished) { _finished=true;_source.clear();_captured=QDateTime::currentMSecsSinceEpoch(); }
        }
    }
    QVariantMap poll(const QVariantMap& command) {
        if (!gui() || !same(command)) { return {}; }
        if (!_finished || !_destroyed) { return {{"pending",true},{"requestId",command.value("commandId")}}; }
        const bool valid=!_source.isEmpty() && _captured>=_requested && _captured-_requested<1500;
        const QVariantMap value{{"schemaVersion",1},{"requestId",_command.value("commandId")},{"runId",_command.value("runId")},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",_requested},{"capturedEpochMs",_captured},
            {"source",_source},{"activeRequests",0},{"retainedResults",0}};
        _deliveredIds.insert(_command.value("commandId").toString());abort();_command.clear();_source.clear();_context.clear();_request=nullptr;_started=false;
        return valid ? value : QVariantMap();
    }
private:
    static bool gui() { return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread(); }
    QVariantMap _command,_source,_context;QObject* _request{nullptr};QPointer<QObject> _cancellation;QString _instance;QSet<QString> _deliveredIds;
    quint64 _sequence{0};qint64 _requested{0},_captured{0};bool _rejected{false},_started{false},_finished{false},_destroyed{false};
};
} // namespace overte::e2e
#endif
