// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonArray>
#include <QJsonObject>
#include <QPointer>
#include <QQuickItem>
#include <QQuickWindow>
#include <QQmlContext>
#include <QQmlEngine>
#include <QThread>
#include <QUuid>
#include <functional>

namespace overte::e2e {
// Weak identities describe the actual canonical Audio.qml component. They do
// not turn invisibility/detachment or one dead object into context retirement.
class AudioPageObservation {
public:
    explicit AudioPageObservation(const QUrl& source):_source(source) {}
    QJsonObject observe(QQuickItem* root,QQuickWindow* window,bool open) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")
                || QThread::currentThread()!=QCoreApplication::instance()->thread() || !_valid || !_source.isValid()
                || (root && root->thread()!=QThread::currentThread()) || (window && window->thread()!=QThread::currentThread())
                || _sequence>=9007199254740991ULL) { return {}; }
        bool complete{true};int count{0};
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if (!item || !complete) { return; }
            if (++count>4096 || depth>128 || item->thread()!=QThread::currentThread()) { complete=false;return; }
            auto context=canonical(item);
            if (context) {
                bool known{false};for(const auto& original:_originals) { if(original.page==item) {known=true;break;} }
                if (!known) {
                    const auto peak=item->property("peakValuesWereEnabled");
                    if (_originals.size()>=64 || !root || !window || peak.userType()!=QMetaType::Bool) {complete=false;return;}
                    Original original;original.id=nonce();original.page=item;original.context=context;original.root=root;original.window=window;
                    original.pageId=identity(item);original.contextId=identity(context);original.rootId=identity(root);original.windowId=identity(window);
                    if(original.pageId.isEmpty()||original.contextId.isEmpty()||original.rootId.isEmpty()||original.windowId.isEmpty()) {complete=false;return;}
                    original.peak=peak.toBool();original.first=QDateTime::currentMSecsSinceEpoch();_originals.append(original);
                }
            }
            for(auto child:item->childItems()) {walk(child,depth+1);}
        };
        walk(root,0);if (!complete) {_valid=false;return {};}
        const auto now=QDateTime::currentMSecsSinceEpoch();if(now<=0||now<_epoch) {_valid=false;return {};}_epoch=now;
        QJsonArray rows;QString current;
        for(const auto& original:_originals) {
            bool attached{false},visible{false};
            if (original.page && original.context) {
                if(canonical(original.page)!=original.context || original.page->property("peakValuesWereEnabled").userType()!=QMetaType::Bool
                        || original.page->property("peakValuesWereEnabled").toBool()!=original.peak) {_valid=false;return {};}
                int depth{0};for(auto item=original.page.data();item && ++depth<=128;item=item->parentItem()) {
                    if(item==original.root && original.root==root) {attached=true;break;}
                }
                visible=attached && original.window && original.window==window && original.page->window()==window
                    && original.page->isVisible() && original.page->width()>0 && original.page->height()>0;
                int visibilityDepth{0};
                for(auto item=original.page.data();visible && item && ++visibilityDepth<=128;item=item->parentItem())
                    visible=item->isVisible() && item->opacity()>.01;
            }
            const bool selected=open && visible;
            if(selected) {if(!current.isEmpty()) {_valid=false;return {};}current=original.id;}
            rows.append(QJsonObject{{"id",original.id},{"pageId",original.pageId},{"contextId",original.contextId},
                {"rootId",original.rootId},{"windowId",original.windowId},{"firstObservedEpochMs",static_cast<double>(original.first)},
                {"pageAlive",!original.page.isNull()},{"contextAlive",!original.context.isNull()},
                {"rootAlive",!original.root.isNull()},{"windowAlive",!original.window.isNull()},
                {"alive",!original.page.isNull()||!original.context.isNull()},
                {"attached",attached},{"visible",visible},{"current",selected},{"originalPeakValuesEnabled",original.peak}});
        }
        return {{"instance",_instance},{"sequence",static_cast<double>(++_sequence)},{"capturedEpochMs",static_cast<double>(now)},
            {"componentSourceSha256",QString::fromLatin1(QCryptographicHash::hash(_source.toString(QUrl::FullyEncoded).toUtf8(),QCryptographicHash::Sha256).toHex())},
            {"current",current},{"originals",rows}};
    }
private:
    QQmlContext* canonical(QQuickItem* page)const {
        if(!page || page->objectName()!="settings.audio" || page->property("title").toString()!="Audio Settings") {return nullptr;}
        int depth{0};for(auto context=qmlContext(page);context && ++depth<=128;context=context->parentContext()) {
            if(context->thread()==QThread::currentThread() && context->isValid() && context->baseUrl()==_source
                    && context->nameForObject(page)=="root") {return context;}
        }return nullptr;
    }
    static QString nonce(){return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    QString identity(QObject* object) {
        for(const auto& original:_identities) {if(original.object==object) {return original.id;}}
        if(!object||_identities.size()>=256) {return {};}
        const auto id=nonce();_identities.append({object,id});return id;
    }
    struct Identity {QPointer<QObject> object;QString id;};
    struct Original {
        QString id,pageId,contextId,rootId,windowId;
        QPointer<QQuickItem> page,root;QPointer<QQmlContext> context;QPointer<QQuickWindow> window;
        qint64 first{0};bool peak{false};
    };
    QUrl _source;QString _instance{nonce()};quint64 _sequence{0};qint64 _epoch{0};bool _valid{true};
    QList<Identity> _identities;QList<Original> _originals;
};
} // namespace overte::e2e
#endif
