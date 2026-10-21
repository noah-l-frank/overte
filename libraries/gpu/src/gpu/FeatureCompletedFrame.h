// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "Backend.h"
#include "FeatureCompletedDrawTrace.h"
#include <QCoreApplication>
#include <QBuffer>
#include <QCryptographicHash>
#include <QImage>
#include <QDateTime>
#include <QElapsedTimer>
#include <QHash>
#include <QJsonDocument>
#include <QList>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QSet>
#include <QUuid>
#include <memory>

namespace gpu {
// One requested original main forward frame. Recording/submission do not
// publish completion. The existing Vulkan fence wait must actually succeed.
// Frame and window callbacks retain the ticket until their real destruction.
class FeatureCompletedFrames : public std::enable_shared_from_this<FeatureCompletedFrames> {
public:
    struct Ticket {
        std::weak_ptr<FeatureCompletedFrames> owner;
        QString id;
        QVariantMap metadata;
        std::shared_ptr<FeatureFramebufferReadback> readback;
        qint64 submittedEpoch {0};
        quint32 frameIndex {0};
        bool submitted {false},completed {false};
        ~Ticket() {
            readback.reset();
            metadata.clear();
            if (auto state=owner.lock()) { state->drained(id,submitted,completed); }
        }
        void record(Backend* backend,const FramebufferPointer& source,const FramebufferPointer& target,
                const Vec4i& viewport,const std::shared_ptr<FeatureCompletedDrawTrace>& trace) {
            if (auto state=owner.lock()) { state->record(*this,backend,source,target,viewport,trace); }
        }
        bool submit(quint32 index) { if (auto state=owner.lock()) { return state->submit(*this,index); }return false; }
        void finish(bool success) { if (auto state=owner.lock()) { state->finish(*this,success); } }
    };

    ~FeatureCompletedFrames() {
        // Unknown GPU submissions cannot become safe through Context/source
        // destruction. Quarantine their actual allocations until process exit.
        // This intentionally leaked test-only holder is never evidence of drain.
        static auto* mutex=new QMutex();
        static auto* unproven=new QList<std::shared_ptr<FeatureFramebufferReadback>>();
        QMutexLocker lock(mutex);
        for (auto it=_readbacks.begin();it!=_readbacks.end();++it) { if (it.value()) { unproven->append(it.value()); } }
    }

    QVariantMap request(const QVariantMap& command) {
        QMutexLocker lock(&_mutex);
        if (!enabled()) { return {}; }
        const auto id=command.value("requestId").toString(),nonce=command.value("commandId").toString();
        const auto operation=command.value("operation").toString();
        const bool pixels=command.value("action").toString()=="feature-vulkan-world-frame";
        if (!valid(id) || !valid(nonce) || _sequence>=1000000000) { return {}; }
        if (_kinds.contains(id) && _kinds.value(id)!=pixels) { return {}; }
        if (operation=="read") {
            if (_retired.contains(id)) { return unavailable(nonce,id); }
            if (_active.isEmpty()) {
                if (_retired.size()>=4096 || !allDrained()) { return unavailable(nonce,id); }
                _active=id;_arm=command;_kinds.insert(id,pixels);_requested=now();_age.start();_packet.clear();_png.clear();_reserved=false;
            }
            if (_active!=id || _arm!=command) { return unavailable(nonce,id); }
            if (!_packet.isEmpty()) { return _packet; } // Untouched original fence time.
            if (_age.elapsed()>=1500) { return unavailable(nonce,id); }
            return {{pixels ? "vulkanWorldFrameVersion" : "completedFrameVersion",1},{"commandId",nonce},{"requestId",id},{"pending",true}};
        }
        if (operation!="release" && operation!="inspect" && !(pixels && operation=="read-bytes")) { return {}; }
        const auto requested=now();
        if (operation=="release") {
            if (!_retired.contains(id) && _retired.size()>=4096) { return {}; }
            _retired.insert(id);
            _kinds.insert(id,pixels);
            if (_active==id) { _active.clear();_arm.clear();_packet.clear();_png.clear(); }
        }
        const bool present=_active==id;
        QVariantMap source {{"retired",_retired.contains(id)},{"present",present},
            {"callbacks",_callbacks.contains(id) ? 1 : 0},
            {"gpuPending",_gpuPending.contains(id)},
            {"metadataBytes",present ? QJsonDocument::fromVariant(_packet).toJson(QJsonDocument::Compact).size() : 0}};
        if (operation=="release") { source.insert("performed",true); }
        if (pixels) {
            const auto readback=_readbacks.value(id);
            source.insert("gpuBufferBytes",readback ? readback->bytes() : 0);
            source.insert("pngBytes",present ? _png.size() : 0);
            if (operation=="read-bytes") {
                const auto offset=command.value("offset").toLongLong();
                if (!present || _png.isEmpty() || offset<0 || offset>=_png.size()) { return {}; }
                source.insert("offset",offset);source.insert("data",QString::fromLatin1(_png.mid(static_cast<int>(offset),65536).toBase64()));
            }
        }
        return {{pixels ? "vulkanWorldStorageVersion" : "frameStorageVersion",1},{"commandId",nonce},{"requestId",id},{"operation",operation},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
            {"capturedEpochMs",now()},{"source",source}};
    }

    std::shared_ptr<Ticket> reserve() {
        QMutexLocker lock(&_mutex);
        if (!enabled() || _active.isEmpty() || _reserved || _age.elapsed()>=1500) { return {}; }
        auto ticket=std::make_shared<Ticket>();ticket->owner=shared_from_this();ticket->id=_active;
        _callbacks.insert(_active);_reserved=true;return ticket;
    }

private:
    static qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
    static bool enabled() { return QCoreApplication::arguments().contains("--testScript"); }
    static bool valid(const QString& value) { return QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(value).hasMatch(); }
    static QVariantMap unavailable(const QString& nonce,const QString& id) {
        return {{"completedFrameVersion",1},{"commandId",nonce},{"requestId",id},{"available",false}};
    }
    bool allDrained() const {
        return _gpuPending.isEmpty() && _callbacks.isEmpty() && _readbacks.isEmpty();
    }
    void record(Ticket& ticket,Backend* backend,const FramebufferPointer& source,const FramebufferPointer& target,
            const Vec4i& viewport,const std::shared_ptr<FeatureCompletedDrawTrace>& trace) {
        QMutexLocker lock(&_mutex);
        if (_active!=ticket.id || _retired.contains(ticket.id) || ticket.submitted || !ticket.metadata.isEmpty()
                || !backend || backend!=Backend::featureExecutingBackend() || !trace) { return; }
        Vec2i actualSource(0),actualTarget(0);
        // This hook is implemented only for successful original Vulkan GPU
        // allocations. No sync/create, requested texture sizes or GL fallback.
        if (!backend->featureFramebufferExtent(source,actualSource)
                || !backend->featureFramebufferExtent(target,actualTarget,true)
                || viewport!=Vec4i(0,0,actualSource.x,actualSource.y)) { return; }
        const auto execution=trace->snapshot(backend);
        if (execution.isEmpty()) { return; }
        ticket.metadata={{"backend","vulkan"},{"stage","tone-map-before-hud"},{"view","main-mono"},
            {"sourceExtent",QVariantList{actualSource.x,actualSource.y}},
            {"targetExtent",QVariantList{actualTarget.x,actualTarget.y}},{"renderTrace",execution}};
        if (_kinds.value(ticket.id)) {
            ticket.readback=backend->featureCopyFramebuffer(target);
            if (!ticket.readback) { ticket.metadata.clear();return; }
            _readbacks.insert(ticket.id,ticket.readback);
        }
    }
    bool submit(Ticket& ticket,quint32 frameIndex) {
        QMutexLocker lock(&_mutex);
        if (ticket.submitted) { return false; }
        ticket.submitted=true;ticket.frameIndex=frameIndex;ticket.submittedEpoch=now();
        _gpuPending.insert(ticket.id);return true;
    }
    void finish(Ticket& ticket,bool success) {
        QMutexLocker lock(&_mutex);
        if (!success || !ticket.submitted || ticket.completed) { return; }
        ticket.completed=true;_gpuPending.remove(ticket.id);
        const auto completed=now();
        const bool pixels=_kinds.value(ticket.id);
        QImage original;QByteArray png,pixelHash;
        const bool wanted=_active==ticket.id && !_retired.contains(ticket.id) && !ticket.metadata.isEmpty()
            && _age.elapsed()<1500 && _sequence<1000000000;
        bool copied=!pixels;
        if (pixels && wanted && ticket.readback) {
            copied=ticket.readback->complete(original);
            if (copied && original.format()==QImage::Format_RGBA8888 && original.bytesPerLine()==original.width()*4) {
                pixelHash=QCryptographicHash::hash(QByteArray::fromRawData(
                    reinterpret_cast<const char*>(original.constBits()),original.width()*original.height()*4),QCryptographicHash::Sha256).toHex();
                QBuffer buffer(&png);
                if (!buffer.open(QIODevice::WriteOnly) || !original.save(&buffer,"PNG")) { png.clear(); }
            }
        }
        const auto width=original.width(),height=original.height();original=QImage();
        const auto pixelsRead=now();
        // The fence actually succeeded: all copy allocations may now drain,
        // including failed/cancelled acquisitions. No extra GPU wait is used.
        ticket.readback.reset();_readbacks.remove(ticket.id);
        if (_active!=ticket.id || _retired.contains(ticket.id) || ticket.metadata.isEmpty()
                || _age.elapsed()>=1500 || _sequence>=1000000000) { return; }
        if (pixels && (!copied || png.isEmpty() || png.size()>33554432)) { return; }
        const auto trace=ticket.metadata.value("renderTrace").toMap();
        if (!(_requested<=trace.value("recordedEpochMs").toLongLong()
                && trace.value("completedEpochMs").toLongLong()<=ticket.submittedEpoch
                && ticket.submittedEpoch<=completed)) { return; }
        auto source=ticket.metadata;
        source.insert("frameIndex",ticket.frameIndex);source.insert("submittedEpochMs",ticket.submittedEpoch);
        source.insert("fenceObservedEpochMs",completed);
        if (pixels) {
            source.insert("pixelFormat","rgba8-top-left");source.insert("pixelsReadEpochMs",pixelsRead);
            source.insert("image",QVariantMap{{"bytes",png.size()},{"sha256",QString::fromLatin1(QCryptographicHash::hash(png,QCryptographicHash::Sha256).toHex())},
                {"pixelSha256",QString::fromLatin1(pixelHash)},{"width",width},{"height",height}});
            _png=std::move(png);
        }
        _packet={{pixels ? "vulkanWorldFrameVersion" : "completedFrameVersion",1},{"commandId",_arm.value("commandId")},{"requestId",ticket.id},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",_requested},
            {"capturedEpochMs",pixels ? now() : completed},{"source",source}};
    }
    void drained(const QString& id,bool submitted,bool completed) {
        QMutexLocker lock(&_mutex);
        // A discarded, never-submitted frame has no GPU consumer. Losing a
        // submitted fence proof keeps responsibility sticky until process death.
        if (!submitted || completed) { _gpuPending.remove(id);_readbacks.remove(id); }
        _callbacks.remove(id);
    }
    QMutex _mutex;
    QString _instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'),_active;
    QVariantMap _arm,_packet;
    qint64 _requested {0};quint64 _sequence {0};bool _reserved {false};QElapsedTimer _age;
    QSet<QString> _retired,_gpuPending,_callbacks;
    QHash<QString,bool> _kinds;
    QHash<QString,std::shared_ptr<FeatureFramebufferReadback>> _readbacks;
    QByteArray _png;
};
} // namespace gpu
#endif
