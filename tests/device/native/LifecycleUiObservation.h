// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QMap>
#include <QPointer>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickWindow>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <cmath>
#include <functional>

namespace overte::e2e {
// Passive source. Canonical URLs come only from native PathUtils at binding,
// not from the command or UI text. Tokens name weak original Qt objects.
class LifecycleUiObservation {
public:
    explicit LifecycleUiObservation(QMap<QString,QUrl> sources) : _sources(std::move(sources)) {}
    QVariantMap observe(QQuickItem* root, QQuickWindow* window, bool shown, bool home,
                        const QString& run, const QVariantMap& keyboard) {
        if (!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
                || !QCoreApplication::arguments().contains("--testScript") || !_valid
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                || keyboard.isEmpty() || _sequence>=9007199254740991ULL
                || (root && (!window || root->window()!=window || root->thread()!=QThread::currentThread()))
                || (window && window->thread()!=QThread::currentThread()) || (shown && (!root || !window))) { return {}; }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<=0 || epoch<_lastEpoch) { _valid=false;return {}; } _lastEpoch=epoch;
        QSet<QQuickItem*> visited; QSet<QString> active; int activeCount{0};
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if (!item || visited.contains(item) || !_valid) { return; }
            if (depth>128 || visited.size()>=4096 || item->thread()!=QThread::currentThread()) { _valid=false;return; }
            visited.insert(item);
            const QString kind=item->objectName()=="NativeCreateText" ? "create"
                : item->objectName()=="chatMessageInput" ? "chat" : item->objectName()=="scriptFilter" ? "scripts" : "";
            if (!kind.isEmpty()) {
                const QString fieldName=kind=="create" ? "newText" : kind=="chat" ? "textArea" : "filter";
                QQmlContext* context{nullptr}; int contexts{0};
                for (auto candidate=qmlContext(item);candidate && ++contexts<=128;candidate=candidate->parentContext()) {
                    if (candidate->thread()!=QThread::currentThread()) { _valid=false;return; }
                    if (candidate->baseUrl()==_sources.value(kind) && candidate->nameForObject(item)==fieldName) { context=candidate;break; }
                }
                if (context && item->window()==window) {
                    QQuickItem* page{nullptr}; QQuickItem* loader{nullptr}; int ancestors{0};
                    for (auto parent=item;parent && ++ancestors<=128;parent=parent->parentItem()) {
                        if (!page && context->nameForObject(parent)=="root") { page=parent; }
                        if (parent->objectName()=="loader") { loader=parent; }
                        if (parent==root) { break; }
                    }
                    if (!page || !loader || !descendant(item,root)) { _valid=false;return; }
                    Entry* entry{nullptr};
                    for (auto& previous:_entries) {
                        if (previous.field==item && previous.page==page && previous.context==context
                                && previous.window==window && previous.loader==loader) { entry=&previous;break; }
                    }
                    if (!entry) {
                        if (_entries.size()>=64) { _valid=false;return; }
                        Entry next;next.kind=kind;next.id=nonce();next.firstObserved=epoch;
                        next.field=item;next.page=page;next.context=context;next.window=window;next.loader=loader;
                        next.fieldId=objectId(item);next.pageId=objectId(page);next.contextId=objectId(context);
                        next.windowId=objectId(window);next.loaderId=objectId(loader);
                        _entries.append(next);entry=&_entries.last();
                    }
                    if (shown && page->isVisible() && descendant(page,root)) { active.insert(entry->id);++activeCount; }
                }
            }
            for (auto child:item->childItems()) { walk(child,depth+1); }
        };
        walk(root,0);
        if (!_valid || activeCount>1 || (home && activeCount)) { return {}; }
        QVariantList rows;QString current;
        for (auto& entry:_entries) {
            const bool alive=entry.field && entry.page && entry.context && entry.window && entry.loader;
            const bool attached=alive && descendant(entry.field,root) && descendant(entry.page,entry.loader);
            const bool visible=alive && visibleField(entry.field,entry.window);
            const bool focused=alive && entry.field->hasActiveFocus();
            const bool selected=active.contains(entry.id);
            QString text;
            if (selected) {
                const auto original=entry.field->property("text");
                if (original.userType()!=QMetaType::QString) { return {}; }
                text=original.toString();
                if (text!="" && text!="retry-"+run && text!="reply-"+run && text!="Overte ä Ω 東京 "+run) { return {}; }
                current=entry.id;
            }
            rows.append(QVariantMap{{"id",entry.id},{"kind",entry.kind},{"fieldId",entry.fieldId},{"pageId",entry.pageId},
                {"contextId",entry.contextId},{"windowId",entry.windowId},{"loaderId",entry.loaderId},
                {"firstObservedEpochMs",entry.firstObserved},{"alive",alive},{"attached",attached},{"visible",visible},
                {"focused",focused},{"current",selected},{"text",text}});
        }
        if (!_valid) { return {}; }
        return {{"lifecycleUiVersion",1},{"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",epoch},{"runId",run},
            {"source",QVariantMap{{"complete",true},{"tabletShown",shown},{"onHomeScreen",home},
                {"current",current},{"editors",rows},{"keyboard",keyboard}}}};
    }
private:
    struct Object { QPointer<QObject> value;QString id; };
    struct Entry {
        QString id,kind,fieldId,pageId,contextId,windowId,loaderId;
        QPointer<QQuickItem> field,page,loader;QPointer<QQuickWindow> window;QPointer<QQmlContext> context;
        qint64 firstObserved{0};
    };
    QString objectId(QObject* value) {
        for (const auto& previous:_objects) { if (previous.value==value) { return previous.id; } }
        if (!value || _objects.size()>=256) { _valid=false;return {}; }
        const auto id=nonce();_objects.append({value,id});return id;
    }
    static bool descendant(QQuickItem* item,QQuickItem* root) {
        if (!root) { return false; }
        for (int depth=0;item && depth<=128;++depth,item=item->parentItem()) { if (item==root) { return true; } }
        return false;
    }
    static bool visibleField(QQuickItem* field,QQuickWindow* window) {
        if (!field || !window || !field->isVisible() || !field->isEnabled()) { return false; }
        auto rect=field->mapRectToScene(field->boundingRect()).intersected(QRectF(0,0,window->width(),window->height()));
        int depth{0};
        for (auto parent=field->parentItem();parent && ++depth<=128;parent=parent->parentItem()) {
            if (!parent->isVisible()) { return false; }
            if (parent->clip()) { rect=rect.intersected(parent->mapRectToScene(parent->boundingRect())); }
        }
        return depth<=128 && !rect.isEmpty() && std::isfinite(rect.x()) && std::isfinite(rect.y())
            && std::isfinite(rect.width()) && std::isfinite(rect.height());
    }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    QMap<QString,QUrl> _sources;QList<Entry> _entries;QList<Object> _objects;
    const QString _instance{nonce()};quint64 _sequence{0};qint64 _lastEpoch{0};bool _valid{true};
};
} // namespace overte::e2e
#endif
