// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NativeReadBracket.h"
#include <QStringList>

namespace overte::e2e {
// A passive copy at the original provider return, never another request.
// The existing native owner alone captures/dispatches/releases the IME event.
class IOSLifecyclePendingCommands {
public:
    static IOSLifecyclePendingCommands& shared() {static IOSLifecyclePendingCommands value;return value;}
    void installed() {_installed=true;}
    void record(const QVariantMap& command,const QVariantMap& reply) {
        if (!_installed || !QStringList{"hold","attempt","release"}.contains(command.value("operation").toString())) {return;}
        const auto id=command.value("commandId").toString();
        for (const auto& entry:_commands) {
            const auto row=entry.toMap();
            if (row.value("command").toMap().value("commandId")==id) {
                if (row.value("command").toMap()!=command || row.value("reply").toMap()!=reply) {_complete=false;}
                return; // The native owner's cached return is not a new input.
            }
        }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (!_complete || reply.isEmpty() || epoch<=0 || epoch<_lastEpoch || _commands.size()>=96) {_complete=false;return;}
        const auto instance=reply.value("instance").toString();
        if (!_owner.isEmpty() && _owner!=instance) {_complete=false;return;}
        _owner=instance;
        const QVariantMap original{{"index",_commands.size()+1},{"command",command},{"reply",reply},{"recordedEpochMs",epoch}};
        const auto bytes=QJsonDocument::fromVariant(original).toJson(QJsonDocument::Compact).size();
        if (_bytes+bytes>131072) {_complete=false;return;}
        _bytes+=bytes;_lastEpoch=epoch;_commands.append(original);
    }
    QVariantMap read(const QString& request,const QString& run) {
        if (!_installed) {return {};}
        return _bracket.read("iosLifecyclePendingCommandsVersion","native-main-lifecycle-pending-commands",request,run,[&]() -> QVariantMap {
            return {{"installed",_installed},{"complete",_complete},{"commands",_commands}};
        });
    }
private:
    NativeReadBracket _bracket;
    QVariantList _commands;
    QString _owner;
    qint64 _lastEpoch {0},_bytes {0};
    bool _installed {false},_complete {true};
};
}
#endif
