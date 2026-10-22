// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QGuiApplication>
#include <QHash>
#include <QMap>
#include <QPointer>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickWindow>
#include <QThread>
#include <QUuid>
#include <QVariantList>
#include <QVariantMap>
#include <memory>
#include <mutex>
#include "PicoCreateFileControls.h"

namespace overte::e2e {
// The real Window response lambda owns a Ticket. Destroying a view/listener
// cannot release a queued native response that has not run to completion.
class CreateDialogs : public std::enable_shared_from_this<CreateDialogs> {
public:
    struct Ticket {
        std::shared_ptr<CreateDialogs> source;QString id;
        std::shared_ptr<void> dispatch() const {return source ? source->dispatch(id) : std::shared_ptr<void>();}
    };
    CreateDialogs() {
        if (gui()) {_instance=identity();_clock.start();}
    }
    Ticket born(QObject* listener,QQuickItem* root,const QString& caption,const QString& filter,bool save) {
        const auto role=!save && caption=="Select .json to Import" ? QStringLiteral("import")
            : save && caption=="Select Where to Save" ? QStringLiteral("export") : QString();
        if (role.isEmpty() || filter!="*.json" || _instance.isEmpty()) {return {};}
        std::lock_guard<std::mutex> lock(_mutex);
        if (!gui() || !_complete || _rows.size()>=32 || !listener || listener->thread()!=qApp->thread()
                || !root || root->thread()!=qApp->thread() || !root->window() || root->window()->thread()!=qApp->thread()) {
            _complete=false;return {};
        }
        const auto context=original(root,role);
        if (!context || !advance()) {_complete=false;return {};}
        for (const auto& known:_rows) {if (known.root==root || known.listener==listener) {_complete=false;return {};}}
        Row row;row.listener=listener;row.root=root;row.context=context;row.window=root->window();
        row.id=identity();row.rootId=objectIdentity(root);row.listenerId=objectIdentity(listener);
        row.contextId=objectIdentity(context);row.windowId=objectIdentity(root->window());
        if (!_complete) {return {};}
        row.role=role;row.source=context->baseUrl().toString(QUrl::FullyEncoded);row.registered=_epoch;
        _rows.insert(row.id,row);return {shared_from_this(),row.id};
    }
    QVariantMap rootIdentity(QQuickItem* root) const {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!gui() || !_complete || !root) {return {};}
        for (const auto& row:_rows) {
            if (row.root==root && row.context && row.window && original(root,row.role)==row.context && root->window()==row.window) {
                return {{"bindingVersion",1},{"sourceInstance",_instance},{"dialogId",row.id},{"rootId",row.rootId},{"listenerId",row.listenerId},
                    {"contextId",row.contextId},{"windowId",row.windowId},{"role",row.role}};
            }
        }
        return {};
    }
    QVariantMap snapshot() {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!gui() || _instance.isEmpty() || !_clock.isValid() || _sequence>=9007199254740991ULL) {return {};}
        QVariantList rows;
        for (const auto& row:_rows) {
            if (row.root && (row.root->thread()!=qApp->thread() || original(row.root,row.role)!=row.context || row.root->window()!=row.window)) {
                _complete=false;
            }
            if (row.listener && row.listener->thread()!=qApp->thread()) {_complete=false;}
            if (row.context && row.context->thread()!=qApp->thread()) {_complete=false;}
            if (row.window && row.window->thread()!=qApp->thread()) {_complete=false;}
            rows.append(QVariantMap{{"id",row.id},{"rootId",row.rootId},{"listenerId",row.listenerId},
                {"contextId",row.contextId},{"windowId",row.windowId},{"role",row.role},{"componentSource",row.source},
                {"registeredEpochMs",row.registered},{"enteredEpochMs",row.entered},{"returnedEpochMs",row.returned},
                {"pending",row.returned==0},{"dispatches",row.dispatches},{"listenerAlive",!row.listener.isNull()},
                {"rootAlive",!row.root.isNull()},{"contextAlive",!row.context.isNull()},{"windowAlive",!row.window.isNull()}});
        }
        return {{"createDialogSourceVersion",1},{"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"elapsedMs",_clock.elapsed()},{"complete",_complete},{"dialogs",_complete ? rows : QVariantList()}};
    }
private:
    struct Row {
        QString id,rootId,listenerId,contextId,windowId,role,source;
        QPointer<QObject> listener;QPointer<QQuickItem> root;QPointer<QQmlContext> context;QPointer<QQuickWindow> window;
        qint64 registered {0},entered {0},returned {0};int dispatches {0};
    };
    static bool enabled() {return qApp && QCoreApplication::arguments().contains("--testScript");}
    static bool gui() {return enabled() && QThread::currentThread()==qApp->thread();}
    static QString identity() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    static QQmlContext* original(QQuickItem* root,const QString& role) {
        return gui() && root && createFileRole(root)==role ? createOriginalFileContext(root) : nullptr;
    }
    bool advance() {
        const auto epoch=QDateTime::currentMSecsSinceEpoch();if (epoch<=0 || epoch<_epoch) {return false;}_epoch=epoch;return true;
    }
    QString objectIdentity(QObject* object) {
        if (!object) {_complete=false;return {};}
        const auto known=_objects.value(object);
        if (known.object==object) {return known.id;}
        if (_objectGenerations>=128) {_complete=false;return {};}
        ++_objectGenerations;const auto id=identity();_objects.insert(object,{object,id});return id;
    }
    // Original Window receivers may run on their Script thread. These two
    // methods touch only locked scalar delivery history; all weak QObject/QML
    // inspection stays in the GUI-only acquisition methods above.
    std::shared_ptr<void> dispatch(const QString& id) {
        {
            std::lock_guard<std::mutex> lock(_mutex);
            if (!enabled() || !_complete || !_rows.contains(id) || _rows[id].entered!=0 || !advance()) {_complete=false;return {};}
            _rows[id].entered=_epoch;_rows[id].dispatches=1;
        }
        const auto self=shared_from_this();
        return std::shared_ptr<void>(new int(0),[self,id](void* value){delete static_cast<int*>(value);self->returned(id);});
    }
    void returned(const QString& id) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!enabled() || !_complete || !_rows.contains(id) || _rows[id].dispatches!=1 || _rows[id].returned!=0 || !advance()) {
            _complete=false;return;
        }
        _rows[id].dispatches=0;_rows[id].returned=_epoch;
    }
    mutable std::mutex _mutex;
    QString _instance;bool _complete {true};quint64 _sequence {0};qint64 _epoch {0};QElapsedTimer _clock;
    QMap<QString,Row> _rows;
    struct ObjectIdentity {QPointer<QObject> object;QString id;};
    QHash<QObject*,ObjectIdentity> _objects;int _objectGenerations {0};
};
} // namespace overte::e2e
#endif
