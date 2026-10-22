// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <QUrl>

namespace overte::e2e {
// Passive actual MyAvatar request/result history. This is deliberately not
// populated from input commands, HTTP delivery, advertised URLs or UI ACKs.
class IOSAvatarModelHistory {
public:
    static IOSAvatarModelHistory& instance() { static IOSAvatarModelHistory source; return source; }

    void bindWatcher(const void* watcher) {
        if (!active()) { return; }
        if (!watcher || (_watcher && _watcher!=watcher)) { _complete=false;return; }
        _watcher=watcher;
    }

    void requested(const QUrl& url) {
        if (!active()) { return; }
        if (_generation >= 256 || url.toEncoded().size() > 2048) { _complete=false;return; }
        ++_generation;_requested=url.toString(QUrl::FullyEncoded);
        append({{"kind","requested"},{"generation",static_cast<double>(_generation)},
            {"requestedUrl",_requested},{"resourceUrl",QVariant()},{"success",QVariant()},
            {"assignment",0},{"resourceIdentity",QVariant()}});
    }

    QVariantMap resourceAssigned(const void* watcher,const QUrl& resource,const QString& identity) {
        if (!active() || watcher!=_watcher) { return {}; }
        if (!_generation || _assignment>=256 || resource.toEncoded().size()>2048 || identity.isEmpty()) {
            _complete=false;return {};
        }
        QVariantMap original {{"kind","assigned"},{"generation",static_cast<double>(_generation)},
            {"requestedUrl",_requested},{"resourceUrl",resource.toString(QUrl::FullyEncoded)},
            {"success",QVariant()},{"assignment",static_cast<double>(++_assignment)},
            {"resourceIdentity",identity}};
        append(original);return original;
    }

    void finished(const QVariantMap& originalAssignment,bool success) {
        if (!active() || originalAssignment.isEmpty()) { return; }
        // The dedicated connection captures this immutable assignment at the
        // original Resource connection, before any result can be delivered.
        // Current MyAvatar/Model properties never select callback provenance.
        auto event=originalAssignment;event["kind"]="finished";event["success"]=success;
        append(event);
    }

    QVariantMap snapshot() const {
        if (!active()) { return {}; }
        return {{"avatarModelHistoryVersion",1},{"instance",_instance},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"currentGeneration",static_cast<double>(_generation)},
            {"eventSequence",static_cast<double>(_sequence)},{"complete",_complete},{"events",_events}};
    }

private:
    IOSAvatarModelHistory() { if (_enabled) { _clock.start(); } }
    bool active() const {
        const auto app=QCoreApplication::instance();
        return _enabled && app && QThread::currentThread()==app->thread()
            && QCoreApplication::arguments().contains("--testScript");
    }
    void append(QVariantMap event) {
        if (_sequence>=512) { _complete=false;return; }
        event["eventSequence"]=static_cast<double>(++_sequence);
        event["epochMs"]=static_cast<double>(QDateTime::currentMSecsSinceEpoch());
        event["monotonicMs"]=static_cast<double>(_clock.elapsed());_events.append(event);
    }
    const bool _enabled {QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript")};
    const QString _instance {_enabled ? QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-') : QString()};
    const void* _watcher {nullptr};QString _requested;QElapsedTimer _clock;
    quint64 _generation {0},_sequence {0},_assignment {0};
    bool _complete {true};QVariantList _events;
};

class IOSAvatarStateObservation {
public:
    QVariantMap read(const QString& request,const QString& run,const std::function<QVariantMap()>& reader) {
        auto value=_bracket.read("iosAvatarStateVersion","native-main-avatar",request,run,[&]() -> QVariantMap {
            const auto source=reader();const auto history=IOSAvatarModelHistory::instance().snapshot();
            if (source.isEmpty() || history.isEmpty()) { return {}; }
            auto result=source;result["modelHistory"]=history;return result;
        });
        if (!value.isEmpty() && value.value("source").toMap().contains("bookmarkFile")) { value["iosAvatarStateVersion"]=2; }
        if (!value.isEmpty() && value.value("source").toMap().contains("sessionPresent")) { value["iosAvatarStateVersion"]=3; }
        return value;
    }
private:
    NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
