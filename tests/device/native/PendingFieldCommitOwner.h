// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "PendingFieldCommitBridge.h"
#include "NormalControlUi.h"
#include <ui/PreparedFieldCommit.h>
#include <ui/NativeFieldInput.h>
#include <PathUtils.h>
#include <QDateTime>
#include <QQmlContext>
#include <QQmlEngine>
#include <map>
#include <memory>

namespace overte::e2e {
// Internal source/ownership component only. The platform supplies actual live
// roots and its existing normal pointer route; callers supply no object paths.
class PendingFieldCommitOwner {
public:
    struct Roots { bool available {false}; QList<QQuickItem*> items; };
    using RootReader = std::function<Roots()>;
    using PointerInput = std::function<bool(QQuickItem*, QQuickWindow*, const QPointF&)>;
    PendingFieldCommitOwner(RootReader roots, PointerInput pointer) : _roots(std::move(roots)), _pointer(std::move(pointer)) {
        _clock.start();
    }

    QVariantMap request(const QVariantMap& command) {
        if (!gui() || _busy || !pendingCommitOwnerCommand(command)) { return {}; }
        const auto id = command.value("commandId").toString(), operation = command.value("operation").toString();
        if (id == _lastId) { return command == _lastCommand ? _lastReply : QVariantMap(); }
        if (_used.contains(id)) { return {}; } // Never replay an older uncertain mutation.
        const auto run = command.value("runId").toString(), event = command.value("eventId").toString();
        const auto record = _records.find(run);
        if (!event.isEmpty() && (record == _records.end() || record->second.event != event)) { return {}; }
        if (operation != "observe" && (command.value("ownerInstance").toString() != _instance
                || command.value("intentSequence").toULongLong() != _intent + 1)) { return {}; }
        // At the query bound, still allow exact owned cleanup. Its native
        // intent cursor prevents replay even without adding another nonce.
        if (_used.size() >= 512 && operation != "release") { return {}; }
        if (!_valid && operation != "release") { return {}; }
        if (_used.size() < 512) { _used.insert(id); }
        _lastId = id; _lastCommand = command; _lastReply.clear();
        _busy = true;
        if (operation != "observe") { ++_intent; } // Consume before any native input or uncertain callback.
        bool performed {false};
        if (operation == "release") {
            performed = record != _records.end() && record->second.prepared->release();
        } else {
            const auto current = currentField(run);
            bool bound = current.field && current.window;
            if (operation != "observe") {
                const auto issued = _issued.constFind(command.value("observationSequence").toULongLong());
                bound = bound && issued != _issued.cend() && issued->run == run
                    && issued->token == command.value("fieldToken").toString() && issued->token == current.token
                    && _clock.elapsed() >= issued->elapsed && _clock.elapsed() - issued->elapsed <= 5000;
            }
            if (operation == "focus" && bound && _pointer) {
                performed = _pointer(current.field, current.window, current.frame.center());
            } else if (operation == "type" && bound) {
                performed = overte::ui::replaceFocusedField(current.field, current.window, "retry-" + run);
            } else if (operation == "hold" && bound && record == _records.end() && _records.size() < 32) {
                bool pending {false}, available {true};
                for (auto& item : _records) {
                    const auto value = item.second.prepared->observation(id);
                    if (value.isEmpty()) { available = false; break; }
                    pending = pending || value.value("pending").toBool();
                }
                if (available && !pending) {
                    auto prepared = overte::ui::prepareFocusedScriptFilterCommit(current.field, current.window, "Overte ä Ω 東京 " + run);
                    if (prepared) {
                        const auto original = prepared->observation(id);
                        if (!original.isEmpty()) {
                            const auto identity = original.value("eventId").toString();
                            _records.emplace(run, Record{id, identity, current.token, std::move(prepared)});
                            performed = true;
                        }
                    }
                }
            } else if (operation == "attempt" && bound && record != _records.end()) {
                performed = record->second.prepared->dispatch(current.field, current.window);
            }
        }
        auto reply = response(command, performed);
        _busy = false;
        _lastReply = reply;
        return reply;
    }

private:
    struct Field {
        QString status {"unavailable"}, token, text;
        QPointer<QQuickItem> field;
        QPointer<QQuickWindow> window;
        QPointer<QQmlContext> context;
        QRectF frame;
    };
    struct Seen { QPointer<QQuickItem> field; QPointer<QQuickWindow> window; QPointer<QQmlContext> context; QString token; };
    struct Issued { QString run, token; qint64 elapsed; };
    struct Record { QString capture, event, token; std::unique_ptr<overte::ui::PreparedFieldCommit> prepared; };

    bool gui() const {
        return qApp && QThread::currentThread() == qApp->thread()
            && QCoreApplication::arguments().contains("--testScript");
    }
    qint64 epoch() {
        const auto now = QDateTime::currentMSecsSinceEpoch();
        if (now <= 0 || now < _lastEpoch || _clock.elapsed() < 0) { _valid = false; return 0; }
        _lastEpoch = now; return now;
    }
    QQmlContext* context(QQuickItem* field) const {
        if (!field || field->thread() != qApp->thread() || field->objectName() != "scriptFilter") { return nullptr; }
        int depth {0};
        for (auto value = qmlContext(field); value && ++depth <= 128; value = value->parentContext()) {
            if (value->thread() != qApp->thread()) { return nullptr; }
            const auto url = value->baseUrl();
            if (value->nameForObject(field) == "filter"
                    && (url.scheme() == "file" || url.scheme() == "qrc") && url.authority().isEmpty()
                    && !url.hasQuery() && !url.hasFragment() && url.toString(QUrl::FullyEncoded).size() <= 4096
                    && url == PathUtils::qmlUrl("hifi/dialogs/TabletRunningScripts.qml")) { return value; }
        }
        return nullptr;
    }
    Field currentField(const QString& run) {
        Field result;
        if (!_roots || !epoch()) { return result; }
        const auto roots = _roots();
        if (!roots.available) { return result; }
        QSet<QQuickItem*> visited;
        bool invalid {false}; int matches {0};
        std::function<void(QQuickItem*, int)> walk = [&](QQuickItem* item, int depth) {
            if (!item || invalid || visited.contains(item)) { return; }
            if (item->thread() != qApp->thread() || depth > 128 || visited.size() >= 4096) { invalid = true; return; }
            visited.insert(item);
            const auto original = context(item);
            auto window = item->window();
            if (original && window && window->thread() == qApp->thread()) {
                const auto frame = NormalControlUi::visibleRect(item, window);
                if (!frame.isEmpty() && item->isEnabled() && !item->property("readOnly").toBool()) {
                    if (++matches > 1) { invalid = true; return; }
                    const auto text = item->property("text");
                    if (text.userType() != QMetaType::QString || (text.toString() != "" && text.toString() != "retry-" + run
                            && text.toString() != "Overte ä Ω 東京 " + run)) { invalid = true; return; }
                    result.field = item; result.window = window; result.context = original;
                    result.text = text.toString(); result.frame = frame;
                }
            }
            for (auto child : item->childItems()) { walk(child, depth + 1); }
        };
        for (auto root : roots.items) { walk(root, 0); }
        if (invalid) { return Field(); }
        if (!matches) { result.status = "none"; return result; }
        for (const auto& old : _seen) {
            if (old.field == result.field && old.window == result.window && old.context == result.context) { result.token = old.token; break; }
        }
        if (result.token.isEmpty()) {
            if (_seen.size() >= 64) { return Field(); }
            result.token = nonce(); _seen.append({result.field, result.window, result.context, result.token});
        }
        result.status = "ready";
        return result;
    }
    QVariantMap response(const QVariantMap& command, bool performed) {
        const auto run = command.value("runId").toString(), id = command.value("commandId").toString();
        const auto current = currentField(run);
        QVariantMap field{{"status", current.status}};
        if (current.status == "ready") {
            field.insert("token", current.token);
            field.insert("componentUrl", current.context->baseUrl().toString(QUrl::FullyEncoded));
            field.insert("text", current.text); field.insert("focused", current.field->hasActiveFocus());
            field.insert("frame", QVariantList{current.frame.x(), current.frame.y(), current.frame.width(), current.frame.height()});
        }
        QVariantMap selected;
        QVariantList pending;
        for (auto& item : _records) {
            const auto original = item.second.prepared->observation(id);
            if (original.isEmpty()) { return {}; } // Unknown inventory cannot become zero.
            if (original.value("pending").toBool()) { pending.append(item.first); }
            if (item.first == run) { selected = {{"captureCommandId", item.second.capture}, {"fieldToken", item.second.token}, {"observation", original}}; }
        }
        const auto captured = epoch();
        if (!_valid || !captured) { return {}; }
        const auto sequence = ++_sequence;
        if (current.status == "ready") {
            _issued.insert(sequence, {run, current.token, _clock.elapsed()});
            for (auto it = _issued.begin(); it != _issued.end();) {
                if (_clock.elapsed() - it->elapsed > 5000) { it = _issued.erase(it); }
                else { ++it; }
            }
            if (_issued.size() > 256) { _issued.clear(); } // Only observation leases; no input history is erased.
        }
        return {{"pendingCommitOwnerVersion", 1}, {"commandId", id}, {"operation", command.value("operation")}, {"runId", run},
            {"instance", _instance}, {"sequence", static_cast<qulonglong>(sequence)}, {"processId", QCoreApplication::applicationPid()},
            {"canonicalComponentUrl", PathUtils::qmlUrl("hifi/dialogs/TabletRunningScripts.qml").toString(QUrl::FullyEncoded)},
            {"capturedEpochMs", captured}, {"lastIntentSequence", static_cast<qulonglong>(_intent)},
            {"performed", command.value("operation").toString() != "observe" && performed},
            {"current", field}, {"commit", selected},
            {"resources", QVariantMap{{"pendingRuns", pending}, {"archivedEvents", static_cast<int>(_records.size())}}}};
    }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    RootReader _roots;
    PointerInput _pointer;
    QElapsedTimer _clock;
    QString _instance {nonce()}, _lastId;
    QVariantMap _lastCommand, _lastReply;
    QSet<QString> _used;
    QVector<Seen> _seen;
    QHash<quint64, Issued> _issued;
    std::map<QString, Record> _records;
    quint64 _sequence {0}, _intent {0};
    qint64 _lastEpoch {0};
    bool _valid {true}, _busy {false};
};
} // namespace overte::e2e
#endif
