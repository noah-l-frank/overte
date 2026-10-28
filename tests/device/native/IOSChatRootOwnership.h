// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSScriptUiRootOwnership.h"
#include <QAbstractItemModel>
#include <QList>
#include <QVariantMap>
#include <qml/IOSQmlSourceObservation.h>
#include <limits>

namespace overte::e2e {
// Reuse the original zeroing-weak ledger. Page/model association is an actual
// QML alias/ListView read, not a QObject-parent claim or a loaded-code identity.
// firstObserved* and weakExpiredObserved* are observations, never birth/death
// timestamps. Hidden and detached operands stay in the ledger while alive.
class IOSChatRootOwnership {
    struct Page {
        QPointer<QQuickItem> item;
        QPointer<QAbstractItemModel> local,domain;
        QString source;
        QVariantMap ids,loadedObjectIdentity;
    };
    script_ui_roots::Ledger _ledger {script_ui_roots::Profile::Chat};
    QList<Page> _pages;
    bool _ready {false},_failed {false},_observeLoadedObjects {false};
    quint64 _census {0};
public:
    void begin(bool observeLoadedObjects=false) noexcept {
        _pages.clear();_ready=true;_observeLoadedObjects=observeLoadedObjects;
        if (_census==std::numeric_limits<quint64>::max()) {_failed=true;_ready=false;return;}
        ++_census;
    }
    quint64 census() const noexcept {
        return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread() ? _census : 0;
    }
    void page(QQuickItem* item,QQuickItem* editor,QAbstractItemModel* local,QAbstractItemModel* domain,const QString& source,bool visible) noexcept {
        if (!script_ui_roots::enabled() || _failed) {return;}
        try {
            if (!item || _pages.size()>=64) {_failed=true;return;}
            for (const auto& page:_pages) {if (page.item==item) {_failed=true;return;}}
            Page row;row.item=item;row.local=local;row.domain=domain;row.source=source;
            if (_observeLoadedObjects) {
                // This is the EXACT item being added by the existing walk,
                // never a URL/SHA/serialized-address association.
                row.loadedObjectIdentity=hifi::qml::IOSQmlSourceObservation::objectIdentity(item);
            }
            row.ids={{"page",_ledger.observe(item,"page",source)},
                {"editor",editor?_ledger.observe(editor,"editor",source):QString()},
                {"localModel",local?_ledger.observe(local,"local-model",source):QString()},
                {"domainModel",domain?_ledger.observe(domain,"domain-model",source):QString()},
                {"list",QString()},{"listModel",QString()},{"visible",visible}};
            if (!editor || !local || !domain) {_ready=false;}
            _pages.append(row);
        } catch (...) {_failed=true;}
    }
    void list(QQuickItem* page,QQuickItem* item,QAbstractItemModel* model) noexcept {
        if (!script_ui_roots::enabled() || _failed) {return;}
        try {
            for (auto& row:_pages) {
                if (row.item!=page) {continue;}
                const auto identity=_ledger.observe(item,"list",row.source);
                const auto previous=row.ids.value("list").toString();
                if (!previous.isEmpty() && previous!=identity) {_ready=false;}
                row.ids["list"]=identity;
                if (model && model==row.local) {row.ids["listModel"]=row.ids.value("localModel");}
                else if (model && model==row.domain) {row.ids["listModel"]=row.ids.value("domainModel");}
                else if (model) {row.ids["listModel"]=_ledger.observe(model,"other-model",row.source);}
                else {_ready=false;}
                return;
            }
            _ready=false;
        } catch (...) {_failed=true;}
    }
    QVariant identity(QQuickItem* item) const noexcept {
        try {
            for (const auto& row:_pages) {if (row.item==item) {
                const auto value=row.ids.value("page").toString();return value.isEmpty()?QVariant():QVariant(value);
            }}
        } catch (...) {}
        return {};
    }
    QVariantMap loadedObjectLinks(quint64 expectedCensus) const noexcept {
        if (!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
                || !script_ui_roots::enabled() || _failed || !_ready || !_observeLoadedObjects
                || !expectedCensus || expectedCensus!=_census) return {};
        try {
            QVariantList links;const auto pages=_pages; // Weak operands and metadata only.
            for (const auto& row:pages) {
                if (!row.item || row.item->thread()!=QThread::currentThread()
                        || row.loadedObjectIdentity.isEmpty()) return {};
                const auto current=hifi::qml::IOSQmlSourceObservation::objectIdentity(row.item.data());
                if (current.isEmpty()) return {};
                auto first=row.loadedObjectIdentity,second=current;
                first.remove("readBefore");first.remove("readAfter");
                second.remove("readBefore");second.remove("readAfter");
                const auto end=row.loadedObjectIdentity.value("readAfter").toMap();
                const auto start=current.value("readBefore").toMap();
                if (first!=second || !row.item || expectedCensus!=_census
                        || end.value("epochMs").toLongLong()>start.value("epochMs").toLongLong()
                        || end.value("monotonicMs").toLongLong()>start.value("monotonicMs").toLongLong()) return {};
                const auto root=row.ids.value("page").toString();if (root.isEmpty()) return {};
                links.append(QVariantMap{{"rootIdentity",root},{"atWalk",row.loadedObjectIdentity},{"atRead",current}});
            }
            if (expectedCensus!=_census) return {};
            return {{"chatRootLoadedObjectLinksVersion",1},{"census",QString::number(_census)},{"links",links}};
        } catch (...) { return {}; }
    }
    QVariantMap read(bool wholeTreeReady) noexcept {
        if (!script_ui_roots::enabled() || _failed) {return {{"iosChatRootOwnershipVersion",1},{"available",false}};}
        try {
            QVariantList pages;
            for (const auto& row:_pages) {
                for (auto it=row.ids.cbegin();it!=row.ids.cend();++it) {if (it.key()!="visible" && it.value().toString().isEmpty()) {_ready=false;}}
                pages.append(row.ids);
            }
            auto result=_ledger.read(wholeTreeReady && _ready);
            if (!result.value("available").toBool()) {return result.toVariantMap();}
            result.insert("pages",QJsonArray::fromVariantList(pages));
            if (QJsonDocument(result).toJson(QJsonDocument::Compact).size()>65536) {
                _failed=true;return {{"iosChatRootOwnershipVersion",1},{"available",false}};
            }
            return result.toVariantMap();
        } catch (...) {_failed=true;return {{"iosChatRootOwnershipVersion",1},{"available",false}};}
    }
};
} // namespace overte::e2e
#endif
