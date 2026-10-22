// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QPointer>
#include <QSharedPointer>
#include <QThread>
#include <QUuid>
#include <QVariantList>
#include <QVariantMap>
#include <atomic>
#include <functional>
#include <memory>
#include <mutex>
#include <vector>

class OffscreenQmlSurface;

namespace overte::ios {
// Cache-owned metadata contains no strong surface, root, renderer or lease.
// Only actual cache operands and actual renderer acquisition operands register
// births. Reading never manufactures a cache entry or promotes a weak owner.
class IOSWebSurfaceOwnership final {
public:
    static constexpr int MAX_SOURCE_BYTES=240000;
    IOSWebSurfaceOwnership() : _state(std::make_shared<State>()) { _state->clock.start(); }
    static bool enabled() {
        const auto args=QCoreApplication::arguments();const auto at=args.indexOf("--testScript");
        return at>=0 && at+1<args.size() && !args[at+1].isEmpty();
    }
    void built(const QString& source,const QSharedPointer<OffscreenQmlSurface>& surface) {
        if (!enabled()) { return; }
        auto& data=*_state;std::lock_guard<std::mutex> guard(data.mutex);
        if (!main(data) || surface.isNull() || source.isEmpty() || find(data,surface.data()) || data.surfaces.size()>=512) {
            data.complete=false;return;
        }
        Surface row;row.id=birth();row.address=surface.data();row.weak=surface;row.source=source;
        data.surfaces.push_back(std::move(row));event(data,"built",data.surfaces.back());
    }
    void cached(const QSharedPointer<OffscreenQmlSurface>& surface,const QString& kind) {
        if (!enabled()) { return; }
        auto& data=*_state;std::lock_guard<std::mutex> guard(data.mutex);auto* row=find(data,surface.data());
        if (!main(data) || !row || (kind!="reserved" && kind!="released") || row->cached) { data.complete=false;return; }
        row->cached=true;event(data,kind,*row);
    }
    void acquired(const QSharedPointer<OffscreenQmlSurface>& surface) {
        if (!enabled()) { return; }
        auto& data=*_state;std::lock_guard<std::mutex> guard(data.mutex);auto* row=find(data,surface.data());
        if (!main(data) || !row || !row->cached) { data.complete=false;return; }
        row->cached=false;event(data,"acquired",*row);
    }
    std::function<void(QObject*)> rootCallback(const QSharedPointer<OffscreenQmlSurface>& surface) {
        if (!enabled()) { return {}; }
        auto& data=*_state;std::lock_guard<std::mutex> guard(data.mutex);auto* row=find(data,surface.data());
        if (!main(data) || !row) { data.complete=false;return {}; }
        const auto id=row->id;const std::weak_ptr<State> weak=_state;
        return [weak,id](QObject* root) {
            auto owner=weak.lock();if (!owner) { return; }
            auto& data=*owner;std::lock_guard<std::mutex> guard(data.mutex);
            if (!main(data) || !root) { data.complete=false;return; }
            for (auto& row:data.surfaces) {
                if (row.id!=id) { continue; }
                if (row.weak.isNull()) { data.complete=false;return; }
                if (row.rootId.isEmpty()) { row.rootId=birth();row.root=root;event(data,"root-created",row); }
                else if (row.root!=root) { data.complete=false; }
                return;
            }
            data.complete=false;
        };
    }
    void rendererLease(const QSharedPointer<OffscreenQmlSurface>& surface,const QSharedPointer<int>& lease,
            const QString& entity,const QString& source) {
        if (!enabled()) { return; }
        auto& data=*_state;std::lock_guard<std::mutex> guard(data.mutex);auto* row=find(data,surface.data());
        if (!main(data) || !row || row->cached || lease.isNull() || entity.isEmpty() || source.isEmpty()
                || data.leases.size()>=2048) { data.complete=false;return; }
        for (const auto& old:data.leases) {
            if (old.address==lease.data() && !old.weak.isNull()) { data.complete=false;return; }
        }
        Lease value;value.id=birth();value.surface=row->id;value.address=lease.data();value.weak=lease;value.entity=entity;value.source=source;
        data.leases.push_back(std::move(value));event(data,"renderer-acquired",*row,data.leases.back().id);
    }
    QVariantMap read() const {
        if (!enabled()) { return {}; }
        auto& data=*_state;std::lock_guard<std::mutex> guard(data.mutex);
        if (!main(data) || data.sequence>=1000000000) { data.complete=false;return {}; }
        QVariantList surfaces,leases;
        for (const auto& row:data.surfaces) {
            surfaces.append(QVariantMap{{"birth",row.id},{"rootSource",row.source},{"cached",row.cached},
                {"surfaceAlive",!row.weak.isNull()},{"rootBirth",row.rootId},{"rootAlive",!row.root.isNull()}});
        }
        for (const auto& row:data.leases) {
            leases.append(QVariantMap{{"birth",row.id},{"surfaceBirth",row.surface},{"entityId",row.entity},
                {"sourceUrl",row.source},{"alive",!row.weak.isNull()}});
        }
        const auto now=QDateTime::currentMSecsSinceEpoch();if (now<=0 || now<data.epoch) { data.complete=false; }
        else { data.epoch=now; }
        const QVariantMap result{{"iosWebSurfaceOwnershipVersion",1},{"instance",data.instance},{"sequence",static_cast<double>(++data.sequence)},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"capturedEpochMs",static_cast<double>(now)},
            {"monotonicMs",static_cast<double>(data.clock.elapsed())},{"complete",data.complete.load()},
            {"eventSequence",static_cast<double>(data.events.size())},{"events",data.events},{"surfaces",surfaces},{"leases",leases}};
        // Keep the unchanged NativeReadBracket's full 250000-byte envelope
        // limit. A growing cumulative ledger becomes unavailable, not clipped.
        if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()>MAX_SOURCE_BYTES) {
            data.complete=false;return {};
        }
        return result;
    }
private:
    struct Surface {
        QString id,source,rootId;OffscreenQmlSurface* address{nullptr};QWeakPointer<OffscreenQmlSurface> weak;
        QPointer<QObject> root;bool cached{false};
    };
    struct Lease { QString id,surface,entity,source;int* address{nullptr};QWeakPointer<int> weak; };
    struct State {
        std::mutex mutex;std::atomic_bool complete{true};const QString instance{birth()};QElapsedTimer clock;
        quint64 sequence{0};qint64 epoch{0};std::vector<Surface> surfaces;std::vector<Lease> leases;QVariantList events;
    };
    static QString birth() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool main(State& data) {
        const auto app=QCoreApplication::instance();const bool valid=app && QThread::currentThread()==app->thread();
        if (!valid) { data.complete=false; }return valid;
    }
    static Surface* find(State& data,OffscreenQmlSurface* address) {
        for (auto& row:data.surfaces) { if (row.address==address && !row.weak.isNull()) { return &row; } }return nullptr;
    }
    static void event(State& data,const QString& kind,const Surface& row,const QString& lease={}) {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<data.epoch || data.events.size()>=8192) { data.complete=false;return; }
        data.epoch=now;data.events.append(QVariantMap{{"sequence",data.events.size()+1},{"kind",kind},{"surfaceBirth",row.id},
            {"rootBirth",row.rootId},{"leaseBirth",lease},{"epochMs",static_cast<double>(now)},
            {"monotonicMs",static_cast<double>(data.clock.elapsed())}});
    }
    std::shared_ptr<State> _state;
};
} // namespace overte::ios
#endif
