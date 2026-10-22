// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QUuid>
#include <QUrl>
#include <QVariantMap>
#include <hfm/HFM.h>
#include <map>
#include <memory>
#include <mutex>

namespace overte::e2e {
inline QString animationObservationNonce() {
    return QCoreApplication::arguments().contains("--testScript")
        ? QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-') : QString();
}

// Identify the original immutable parsed model and the exact bytes actually
// supplied to FBXSerializer. A weak model reference prevents pointer reuse from
// borrowing a retired parse, without keeping resources/animation data alive.
class AnimationDataObservation {
public:
    void record(const HFMModel::Pointer& model, const QUrl& url, const QByteArray& bytes, bool skippedCurveData) {
        if (!QCoreApplication::arguments().contains("--testScript") || !model || bytes.isEmpty() || url.toString().size()>4096
                || bytes.size()>32*1024*1024 || model->animationFrames.isEmpty() || model->animationFrames.size()>1000000
                || model->joints.isEmpty() || model->joints.size()>10000) { return; }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();if (epoch<=0) { return; }
        const QVariantMap source{{"animationDataVersion",1},{"instance",animationObservationNonce()},
            {"sourceUrlSha256",QString::fromLatin1(QCryptographicHash::hash(url.toString().toUtf8(),QCryptographicHash::Sha256).toHex())},
            {"bytes",bytes.size()},{"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())},
            {"parser",skippedCurveData ? "fbx-skip-unused-curves-v1" : "fbx-full-v1"},
            {"frames",model->animationFrames.size()},{"joints",model->joints.size()},{"parsedEpochMs",epoch}};
        std::lock_guard<std::mutex> lock(_mutex);
        for (auto it=_models.begin();it!=_models.end();) {
            if (it->second.model.expired()) { it=_models.erase(it); } else { ++it; }
        }
        const auto old=_models.find(model.get());
        if (old!=_models.end()) {
            // A model must never acquire a different source identity. Repeated
            // publication is uncertain, rather than a newly timed observation.
            old->second.source.clear();return;
        }
        if (_models.size()>=1024) { return; } // Never evict a live original.
        _models.emplace(model.get(),Entry{model,source});
    }

    QVariantMap source(const HFMModel* original) const {
        if (!QCoreApplication::arguments().contains("--testScript") || !original) { return {}; }
        std::lock_guard<std::mutex> lock(_mutex);const auto row=_models.find(original);
        if (row==_models.end()) { return {}; }
        const auto model=row->second.model.lock();
        return model && model.get()==original ? row->second.source : QVariantMap();
    }

private:
    struct Entry { std::weak_ptr<HFMModel> model; QVariantMap source; };
    mutable std::mutex _mutex;
    std::map<const HFMModel*,Entry> _models;
};

inline AnimationDataObservation& animationDataObservation() {
    static AnimationDataObservation value;return value;
}
} // namespace overte::e2e
#endif
