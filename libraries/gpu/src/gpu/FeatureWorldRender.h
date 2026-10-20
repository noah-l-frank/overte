// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "Backend.h"
#include "FeatureRenderTrace.h"
#include <QBuffer>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QImage>
#include <QJsonObject>
#include <QJsonDocument>
#include <QHash>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QSet>
#include <QUuid>
#include <QVariantMap>

namespace gpu {
// One bounded, explicitly owned acquisition per recording context. Only the
// actual later GPU callback may publish pixels. No rendered feature verdicts.
class FeatureWorldRender : public std::enable_shared_from_this<FeatureWorldRender> {
public:
    struct Ticket {
        std::weak_ptr<FeatureWorldRender> owner;
        QString id;
        qint64 recorded {0};
        ~Ticket() { if (auto state = owner.lock()) { state->drained(id); } }
        void execute(Backend* backend, const TexturePointer& source,
                const FramebufferPointer& destination, const Vec4i& viewport,
                const std::shared_ptr<FeatureRenderTrace>& trace = {}) {
            if (auto state = owner.lock()) { state->acquire(id,recorded,backend,source,destination,viewport,trace); }
        }
    };

    QVariantMap request(const QString& id) {
        QMutexLocker lock(&_mutex);
        if (!enabled() || !valid(id) || _retired.contains(id)) { return {}; }
        if (_active.isEmpty()) {
            // A cancelled queued/executing callback must drain before reuse.
            if (!_callback.isEmpty() || _retired.size() >= 256) { return {}; }
            _active = id; _requested = now(); _age.start(); _result.clear(); _png.clear();
        }
        if (_active != id) { return {}; }
        if (!_result.isEmpty()) { return _result; } // Original times, never retimed.
        if (_age.elapsed() >= 1500) { fail(id); return _result; }
        return {{"requestId",id},{"pending",true}};
    }

    std::shared_ptr<Ticket> reserve() {
        QMutexLocker lock(&_mutex);
        if (!enabled() || _active.isEmpty() || !_callback.isEmpty() || !_result.isEmpty()) { return {}; }
        if (_age.elapsed() >= 1500) { fail(_active); return {}; }
        _callback = _active;
        auto ticket = std::make_shared<Ticket>();
        ticket->owner = shared_from_this(); ticket->id = _active; ticket->recorded = now();
        return ticket;
    }

    // A closed memory transport: logical nonce PNG names are never filesystem
    // paths. Chunks are original encoded bytes, not screenshots/re-encodings.
    QVariantMap storage(const QVariantMap& command) {
        QMutexLocker lock(&_mutex);
        const auto action = command.value("operation").toString();
        QSet<QString> keys;
        for (auto i = command.cbegin(); i != command.cend(); ++i) { keys.insert(i.key()); }
        QSet<QString> wanted {"schemaVersion","commandId","action","requestId","operation"};
        if (action == "read") { wanted.insert("offset"); }
        const auto id = command.value("requestId").toString();
        const auto nonce = command.value("commandId").toString();
        const auto json = QJsonObject::fromVariantMap(command);
        if (!enabled() || keys != wanted || _receipts.size() >= 65536 || _receipts.contains(nonce)
                || !json.value("schemaVersion").isDouble()
                || json.value("schemaVersion").toDouble() != 1 || !valid(id) || !valid(nonce)
                || command.value("action").toString() != "feature-world-render-storage"
                || (_active != id && !_retired.contains(id) && action != "release")) { return {}; }
        if (action != "read" && action != "release" && action != "inspect") { return {}; }
        if (action == "release" && !_retired.contains(id)) {
            if (_retired.size() >= 256) { return {}; }
            // Retire even an acquisition not yet delivered by the probe. An
            // uncertain/late request cannot allocate pixels after cleanup.
            _retired.insert(id);
        }
        if (action == "release" && _active == id) {
            _active.clear(); _result.clear(); _png.clear();
            // A queued lambda keeps its ticket until execution or batch discard.
        }
        QVariantMap value {{"storageVersion",1},{"commandId",nonce},{"requestId",id},{"instance",_instance},
            {"sequence",static_cast<qulonglong>(++_storageSequence)}, {"processId",QCoreApplication::applicationPid()},
            {"capturedEpochMs",now()}, {"present",_active == id}, {"callbacks",_callback == id ? 1 : 0},
            {"pngBytes",_active == id ? _png.size() : 0}};
        if (action == "read") {
            bool okay {false}; const auto offset = command.value("offset").toLongLong(&okay);
            // JSON numbers arrive as double through some script engines. Reject
            // fractional/coerced strings even when QVariant can convert them.
            const auto type = command.value("offset").type();
            if (!okay || (type != QVariant::Int && type != QVariant::LongLong && type != QVariant::Double)
                    || command.value("offset").toDouble() != static_cast<double>(offset)
                    || _active != id || _png.isEmpty() || offset < 0 || offset >= _png.size()) { return {}; }
            value.insert("offset",offset);
            value.insert("data",QString::fromLatin1(_png.mid(static_cast<int>(offset),65536).toBase64()));
        }
        _receipts.insert(nonce,qMakePair(id,QCryptographicHash::hash(
            QJsonDocument::fromVariant(value).toJson(),QCryptographicHash::Sha256).toHex()));
        return value;
    }

    QByteArray receiptDigest(const QString& capture, const QString& nonce, bool requireRetired = true) {
        QMutexLocker lock(&_mutex);
        const auto found = _receipts.constFind(nonce);
        if (found == _receipts.cend() || found.value().first != capture
                || (requireRetired && !_retired.contains(capture))) { return {}; }
        return found.value().second;
    }
    QString instance() const { return _instance; }

private:
    static qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
    static bool enabled() { return QCoreApplication::arguments().contains("--testScript"); }
    static bool valid(const QString& id) { return QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch(); }
    static QString sha(const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()); }
    void fail(const QString& id) {
        if (_active == id) { _result = {{"schemaVersion",1},{"requestId",id},{"available",false}}; }
    }
    void drained(const QString& id) {
        QMutexLocker lock(&_mutex);
        if (_callback == id) { _callback.clear(); }
    }
    void acquire(const QString& id, qint64 recorded, Backend* backend,
            const TexturePointer& source, const FramebufferPointer& destination, const Vec4i& viewport,
            const std::shared_ptr<FeatureRenderTrace>& trace) {
        qint64 requested {0};
        {
            QMutexLocker lock(&_mutex);
            if (_active != id || _callback != id || !_result.isEmpty()) { return; }
            if (_age.elapsed() >= 1500) { fail(id); return; }
            requested = _requested;
        }
        const auto started = now();
        Vec2i actualExtent(0); QImage pixels;
        const bool read = backend && backend == Backend::featureExecutingBackend()
            && backend->featureTextureExtent(source,actualExtent)
            && viewport.x >= 0 && viewport.y >= 0 && viewport.z > 0 && viewport.w > 0
            && viewport.x <= actualExtent.x-viewport.z && viewport.y <= actualExtent.y-viewport.w
            && backend->featureReadFramebuffer(destination,pixels);
        const auto captured = now();
        QByteArray png, pixelHash;
        int width {0}, height {0};
        if (read && pixels.format() == QImage::Format_RGBA8888 && pixels.bytesPerLine() == pixels.width()*4) {
            width = pixels.width(); height = pixels.height();
            pixelHash = QCryptographicHash::hash(QByteArray::fromRawData(
                reinterpret_cast<const char*>(pixels.constBits()),width*height*4),QCryptographicHash::Sha256).toHex();
            QBuffer buffer(&png);
            if (!buffer.open(QIODevice::WriteOnly) || !pixels.save(&buffer,"PNG")) { png.clear(); }
        }
        pixels = QImage(); // The ticket remains live through all temporary buffers.
        QMutexLocker lock(&_mutex);
        if (_active != id || !_result.isEmpty()) { return; } // Cancelled/expired: discard originals.
        const auto published = now();
        if (!read || png.isEmpty() || png.size() > 33554432 || _age.elapsed() >= 1500
                || !(requested <= recorded && recorded <= started && started <= captured && captured <= published)) {
            fail(id); return;
        }
        const auto normalized = id.startsWith("ios-") ? id.mid(4) : id;
        const QVariantMap image {{"name","world-render-image-"+normalized+".png"},{"bytes",png.size()},
            {"sha256",sha(png)},{"pixelSha256",QString::fromLatin1(pixelHash)},{"width",width},{"height",height}};
        const auto execution = trace ? trace->snapshot(backend) : QVariantMap();
        // A declared forward trace must have actually reached the GPU. Do not
        // downgrade a missing/discarded begin marker to the legacy protocol.
        if (trace && execution.isEmpty()) { fail(id); return; }
        QVariantMap observation {{"captureVersion",trace ? 2 : 1},{"available",true},
            {"acquisitionSequence",static_cast<qulonglong>(++_acquisitions)}, {"recordedEpochMs",recorded},
            {"startedEpochMs",started},{"capturedEpochMs",captured},{"backend","opengl"},
            {"stage","tone-map-before-hud"},{"view","main-mono"},
            {"sourceExtent",QVariantList{actualExtent.x,actualExtent.y}},
            {"sourceViewport",QVariantList{viewport.x,viewport.y,viewport.z,viewport.w}},
            {"targetExtent",QVariantList{width,height}},{"pixelFormat","rgba8-top-left"},{"image",image}};
        if (trace) { observation.insert("renderTrace",execution); }
        _png = std::move(png);
        _result = {{"schemaVersion",1},{"requestId",id},{"instance",_instance},
            {"sequence",static_cast<qulonglong>(++_sequence)}, {"requestedEpochMs",requested},
            {"capturedEpochMs",published},{"processId",QCoreApplication::applicationPid()},{"source",observation}};
    }
    QMutex _mutex;
    const QString _instance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QString _active, _callback;
    QSet<QString> _retired; // Bounded; never forget retired nonces to enable replay.
    QElapsedTimer _age;
    qint64 _requested {0};
    quint64 _sequence {0}, _acquisitions {0}, _storageSequence {0};
    QVariantMap _result;
    QByteArray _png;
    QHash<QString,QPair<QString,QByteArray>> _receipts; // Bounded original receipt identities/hashes, not PNG copies.
};
}
#endif
