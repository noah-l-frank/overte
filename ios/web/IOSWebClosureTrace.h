// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>

// Passive callback, native view, policy grant and native bitmap ownership.
// This does not prove software-image or GPU-allocation absence.
// No product policy, navigation or timer is changed.
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
#include "../../tests/device/native/IOSWebClosureBridge.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>
#include <QImage>
#include <shared/IOSFeatureImageTrace.h>
#include <QRegularExpression>
#include <QSet>
#include <QUrl>
#include <QUuid>
#include <QVariantMap>
#include <QVariantList>
#include <array>
#include <atomic>
#include <map>
#include <memory>
#include <mutex>

namespace overte::ios::feature_closures {
constexpr quint64 LIMIT = 9007199254740991ULL;
constexpr std::size_t MAX_CONTEXTS = 1024;
enum class Kind : std::size_t { JavaScript, Snapshot, Presentation, RuleList, Notification, ScriptReply, Download, PolicyGrant, NativeView, NativeBitmap, SceneGraphNode, OffscreenImage, UploadImage, CPUTexture, VulkanTexture, VulkanImage, VulkanView, VulkanSampler, VulkanAllocation, VulkanStagingBuffer, VulkanStagingMemory, VulkanSubmission, NativeDelegate, NativePresentation, NativeSnapshotObject, Count };
inline const std::array<const char*, static_cast<std::size_t>(Kind::Count)> NAMES {
    "javascript", "snapshot", "presentation", "rule-list", "notification", "script-reply", "download", "policy-grant", "native-view", "native-bitmap", "scenegraph-node", "offscreen-image", "upload-image", "cpu-texture", "vulkan-texture", "vulkan-image", "vulkan-image-view",
    "vulkan-sampler", "vulkan-allocation", "vulkan-staging-buffer", "vulkan-staging-memory", "vulkan-submission",
    "native-delegate", "native-presentation", "native-snapshot-object"
};
constexpr std::size_t CALLBACK_KINDS = 7;
struct Counters { quint64 created { 0 }, retired { 0 }; };
struct Row {
    QVariantMap descriptor;
    qint64 createdEpochMs { 0 }, updatedEpochMs { 0 };
    std::array<Counters, static_cast<std::size_t>(Kind::Count)> counters {};
};
struct State {
    std::mutex mutex;
    const QString instance { QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-') };
    quint64 next { 1 }, sequence { 0 };
    qint64 epoch { 0 };
    bool complete { true };
    std::map<quint64, Row> rows;
    std::map<QString, quint64> identities;
};
// Keep bounded test metadata alive through late native block destruction at
// process shutdown. This does not retain a WK view, callback or product buffer.
inline State& state() { static State* value = new State; return *value; }
inline bool enabled() {
    const auto args = QCoreApplication::arguments();
    const auto script = args.indexOf("--testScript"), results = args.indexOf("--testResultsLocation");
    return script >= 0 && script + 1 < args.size() && !args[script + 1].isEmpty()
        && results >= 0 && results + 1 < args.size() && !args[results + 1].isEmpty();
}
inline bool ownedURL(const QString& source) {
    const QUrl url(source, QUrl::StrictMode);
    return source.size() <= 1024 && url.toString(QUrl::FullyEncoded) == source
        && url.isValid() && (url.scheme() == "http" || url.scheme() == "https") && !url.host().isEmpty()
        && url.userName().isEmpty() && url.password().isEmpty() && !url.hasQuery() && !url.hasFragment()
        && QRegularExpression("\\A/feature-fixture/v1/runs/[0-9a-f]{32}/tickets/[0-9a-f]{32}/(?:graphics-marker\\.v1|index|reference)\\.html\\z")
            .match(url.path()).hasMatch();
}
struct Context { quint64 id { 0 }; };
using ContextPointer = std::shared_ptr<const Context>;
inline ContextPointer context(quint64 handle, quint64 creation, quint64 grant, quint64 page,
        const QString& surface, const QString& identity, const QString& source) {
    if (!enabled() || !ownedURL(source)) { return {}; }
    auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex);
    const auto now = QDateTime::currentMSecsSinceEpoch();
    if (!handle || !grant || handle > LIMIT || creation > LIMIT || grant > LIMIT || page > LIMIT
            || (surface != "tablet" && surface != "world-entity") || identity.isEmpty() || now <= 0 || now < data.epoch) {
        data.complete = false; return {};
    }
    QVariantMap descriptor {{"handle", static_cast<qulonglong>(handle)}, {"creation", static_cast<qulonglong>(creation)},
        {"grant", static_cast<qulonglong>(grant)}, {"page", static_cast<qulonglong>(page)}, {"surface", surface},
        {"identitySha256", QString::fromLatin1(QCryptographicHash::hash(identity.toUtf8(), QCryptographicHash::Sha256).toHex())},
        {"sourceUrl", source}};
    const auto key = QString::fromUtf8(QJsonDocument(QJsonObject::fromVariantMap(descriptor)).toJson(QJsonDocument::Compact));
    const auto found = data.identities.find(key);
    if (found != data.identities.end()) { return std::make_shared<Context>(Context { found->second }); }
    if (data.rows.size() >= MAX_CONTEXTS || !data.next || data.next > LIMIT) { data.complete = false; return {}; }
    const auto id = data.next++; data.epoch = now;
    Row row; row.descriptor = descriptor; row.createdEpochMs = row.updatedEpochMs = now;
    data.rows.emplace(id, std::move(row)); data.identities.emplace(key, id);
    return std::make_shared<Context>(Context { id });
}
class Lease final {
public:
    Lease(const Lease&) = delete;
    Lease& operator=(const Lease&) = delete;
    Lease(ContextPointer context, Kind kind) : _context(std::move(context)), _kind(kind) {
        auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex);
        const auto found = data.rows.find(_context->id); const auto index = static_cast<std::size_t>(_kind);
        const auto now = QDateTime::currentMSecsSinceEpoch();
        if (found == data.rows.end() || index >= NAMES.size() || now <= 0 || now < data.epoch) { data.complete = false; return; }
        auto& row = found->second; auto& counter = row.counters[index];
        if (counter.created >= LIMIT) { data.complete = false; return; }
        ++counter.created; row.updatedEpochMs = data.epoch = now; _registered = true;
    }
    ~Lease() {
        if (!_registered) { return; }
        auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex);
        auto& row = data.rows.at(_context->id); auto& counter = row.counters[static_cast<std::size_t>(_kind)];
        const auto now = QDateTime::currentMSecsSinceEpoch();
        if (counter.retired >= counter.created || now <= 0 || now < data.epoch) { data.complete = false; return; }
        ++counter.retired; row.updatedEpochMs = data.epoch = now;
    }
private:
    ContextPointer _context;
    Kind _kind;
    bool _registered { false };
};
void nativeObject(void* object, const ContextPointer& context, Kind kind);
inline std::shared_ptr<Lease> retain(const ContextPointer& context, Kind kind) {
    return context ? std::make_shared<Lease>(context, kind) : std::shared_ptr<Lease>();
}
inline feature_images::Scope imageScope(const ContextPointer& context) {
    if (!context) { return {}; }
    const auto id = state().instance + ":" + QString::number(context->id);
    return { id, [context](const QString& kind) -> std::shared_ptr<void> {
        for (std::size_t i = CALLBACK_KINDS; i < NAMES.size(); ++i) {
            if (kind == QLatin1String(NAMES[i])) { return retain(context, static_cast<Kind>(i)); }
        }
        auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex); data.complete = false; return {};
    }, [] { auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex); data.complete = false; } };
}
// A read-only QImage carrier retains the original allocation and a lease until
// the last implicit copy is destroyed. Independently painted/converted images
// need their own source; this carrier cannot prove their allocation absence.
struct BitmapOwner {
    std::shared_ptr<std::atomic<bool>> cleaned;
    std::shared_ptr<Lease> lease;
    QImage original; // Destroy the original reference before retiring its lease.
};
inline QImage nativeBitmap(const QImage& image, const ContextPointer& context) {
    if (!context || image.isNull()) { return image; }
    const auto cleaned = std::make_shared<std::atomic<bool>>(false);
    auto* owner = new BitmapOwner { cleaned, retain(context, Kind::NativeBitmap), image };
    {
        QImage carrier(image.constBits(), image.width(), image.height(), image.bytesPerLine(), image.format(),
            [](void* data) {
                auto* owner = static_cast<BitmapOwner*>(data);
                owner->cleaned->store(true); delete owner;
            }, owner);
        // Native WK snapshot images have the fresh allocation's default metadata.
        // Do not transform pixels, dimensions, row stride, format or timestamps.
        if (!carrier.isNull()) { return carrier; }
    }
    // Handle a failed carrier constructor regardless of whether Qt invoked its
    // external-data cleanup. The failed QImage is already destroyed here.
    if (!cleaned->load()) { delete owner; }
    auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex); data.complete = false;
    return image;
}
inline QVariantMap observe(const QVariantMap& request) {
    if (!enabled() || !command(request)) { return {}; }
    auto& data = state(); std::lock_guard<std::mutex> guard(data.mutex);
    const auto now = QDateTime::currentMSecsSinceEpoch();
    if (now <= 0 || now < data.epoch || data.sequence >= LIMIT) { data.complete = false; return {}; }
    data.epoch = now; QVariantList rows;
    const auto prefix = request.value("fixtureUrl").toString() + "tickets/";
    for (const auto& [id, row] : data.rows) {
        if (!row.descriptor.value("sourceUrl").toString().startsWith(prefix)) { continue; }
        QVariantMap counters, resources;
        for (std::size_t i = 0; i < NAMES.size(); ++i) {
            const auto& counter = row.counters[i];
            auto& collection = i < CALLBACK_KINDS ? counters : resources;
            collection.insert(NAMES[i], QVariantMap {{"created", static_cast<qulonglong>(counter.created)},
                {"retired", static_cast<qulonglong>(counter.retired)}, {"pending", static_cast<qulonglong>(counter.created - counter.retired)}});
        }
        rows.append(QVariantMap {{"id", static_cast<qulonglong>(id)}, {"descriptor", row.descriptor},
            {"createdEpochMs", row.createdEpochMs}, {"updatedEpochMs", row.updatedEpochMs}, {"callbacks", counters}, {"resources", resources}});
    }
    QVariantMap result {{"iosWebClosureVersion", 5}, {"commandId", request.value("commandId")}, {"runId", request.value("runId")},
        {"fixtureUrl", request.value("fixtureUrl")}, {"instance", data.instance}, {"sequence", static_cast<qulonglong>(++data.sequence)},
        {"processId", QCoreApplication::applicationPid()}, {"capturedEpochMs", now}, {"complete", data.complete}, {"contexts", rows}};
    if (QJsonDocument(QJsonObject::fromVariantMap(result)).toJson().size() > 262144) { data.complete = false; return {}; }
    return result;
}
} // namespace overte::ios::feature_closures
#endif
