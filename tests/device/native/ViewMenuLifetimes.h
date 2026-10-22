// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QJSValue>
#include <QJsonArray>
#include <QJsonObject>
#include <QPointer>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickItem>
#include <QThread>
#include <QUuid>
#include <functional>

namespace overte::e2e {
// Passive original TabletMenuStack/StackView/delay Timer/contexts. Invisibility,
// detachment, stopped timers and invalid-but-alive contexts are not destruction.
class ViewMenuLifetimes {
public:
    explicit ViewMenuLifetimes(const QUrl& source):_source(source) {}
    QJsonObject observe(QQuickItem* root) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")
                || QThread::currentThread()!=QCoreApplication::instance()->thread() || !_valid || !_source.isValid()
                || (root && root->thread()!=QThread::currentThread()) || _sequence>=9007199254740991ULL) {return {};}
        const auto epoch=QDateTime::currentMSecsSinceEpoch();if(epoch<=0 || epoch<_epoch) {_valid=false;return {};}_epoch=epoch;
        int visited{0};std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if(!item || !_valid) {return;}
            if(++visited>4096 || depth>128 || item->thread()!=QThread::currentThread()) {_valid=false;return;}
            if(item->objectName()=="tabletMenuHandlerItem") {
                auto context=canonical(item);
                if(context) {
                    QQuickItem* stack{nullptr};
                    for(auto child:item->childItems()) {
                        if(context->nameForObject(child)=="d") {
                            if(stack) {_valid=false;return;}stack=child;
                        }
                    }
                    auto timer=stack ? object(stack->property("delay")) : nullptr;
                    auto timerContext=timer ? qmlContext(timer) : nullptr;
                    if(!stack || stack->objectName()!="stack" || !timer || !timerContext
                            || stack->thread()!=QThread::currentThread() || timer->thread()!=QThread::currentThread()
                            || timerContext->thread()!=QThread::currentThread() || !timer->metaObject()->className()
                            || !QString::fromLatin1(timer->metaObject()->className()).startsWith("QQmlTimer")) {_valid=false;return;}
                    Original* known{nullptr};for(auto& row:_rows) {if(row.page==item) {known=&row;break;}}
                    if(known) {
                        if(known->stack!=stack || known->timer!=timer || known->context!=context || known->timerContext!=timerContext) {_valid=false;return;}
                    } else {
                        if(_rows.size()>=32) {_valid=false;return;}
                        Original row;row.id=nonce();row.first=epoch;row.page=item;row.stack=stack;
                        row.timer=timer;row.context=context;row.timerContext=timerContext;_rows.append(row);
                    }
                }
            }
            for(auto child:item->childItems()) {walk(child,depth+1);}
        };walk(root,0);if(!_valid) {return {};}
        QJsonArray rows;
        for(const auto& original:_rows) {
            bool running{false},pending{false};
            if(original.timer) {
                if(original.timer->thread()!=QThread::currentThread()) {_valid=false;return {};}
                const auto run=original.timer->property("running"),repeat=original.timer->property("repeat"),interval=original.timer->property("interval");
                if(run.userType()!=QMetaType::Bool || repeat.userType()!=QMetaType::Bool || repeat.toBool()
                        || interval.userType()!=QMetaType::Int || interval.toInt()!=0) {_valid=false;return {};}
                running=run.toBool();const auto item=original.timer->property("menuItem");
                if(item.userType()==qMetaTypeId<QJSValue>()) {
                    const auto value=item.value<QJSValue>();
                    if(!value.isNull() && !value.isQObject()) {_valid=false;return {};}
                    pending=value.isQObject() && value.toQObject();
                } else if(item.userType()==qMetaTypeId<QObject*>()) {pending=item.value<QObject*>();}
                else if(item.isValid() && !item.isNull()) {_valid=false;return {};}
            }
            const bool page=original.page,stack=original.stack,timer=original.timer,context=original.context,timerContext=original.timerContext;
            rows.append(QJsonObject{{"instance",original.id},{"firstObservedEpochMs",static_cast<double>(original.first)},
                {"pageAlive",page},{"stackAlive",stack},{"timerAlive",timer},{"contextAlive",context},{"timerContextAlive",timerContext},
                {"alive",page||stack||timer||context||timerContext},{"timerRunning",running},{"pendingMenuItem",pending}});
        }
        return {{"instance",_instance},{"sequence",static_cast<double>(++_sequence)},
            {"capturedEpochMs",static_cast<double>(epoch)},{"originals",rows}};
    }
private:
    QQmlContext* canonical(QQuickItem* item)const {
        // A nested component root has its outer creation context (TabletMenu),
        // whereas its actual StackView child belongs to TabletMenuStack.qml.
        // Qualify the original root AND d in that actual inner source context.
        for(auto child:item->childItems()) {
            int depth{0};for(auto context=qmlContext(child);context && ++depth<=128;context=context->parentContext()) {
                if(context->thread()!=QThread::currentThread()) {return nullptr;}
                if(context->isValid() && context->baseUrl()==_source && context->nameForObject(item)=="root"
                        && context->nameForObject(child)=="d") {return context;}
            }
        }return nullptr;
    }
    static QObject* object(const QVariant& value) {
        if(value.userType()==qMetaTypeId<QJSValue>()) {return value.value<QJSValue>().toQObject();}
        return value.value<QObject*>();
    }
    static QString nonce(){return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    struct Original {
        QString id;qint64 first;QPointer<QQuickItem> page,stack;QPointer<QObject> timer;
        QPointer<QQmlContext> context,timerContext;
    };
    QUrl _source;QString _instance{nonce()};QList<Original> _rows;quint64 _sequence{0};qint64 _epoch{0};bool _valid{true};
};
} // namespace overte::e2e
#endif
