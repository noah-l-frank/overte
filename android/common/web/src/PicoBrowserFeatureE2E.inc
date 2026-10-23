// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Included only by NativeWebViewItem.cpp. Default-off instrumentation; no
// navigation, authority, DOM or feature-state setters are added to the product.
// Document/bridge/inline-lease owner reused from fixed Phone 5527d540e99cc6dba4204a5e904a854e6e1cd2b4.
// Pico actuation is the actual OffscreenQmlSurface pointer and Qt IME route.
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
namespace {
struct WorldWebScope {
    bool reference{false},tablet{false},armed{false},heldPending{false};
    QVariantMap held;QVariantList deliveries;std::function<bool()> replay,leaseCurrent,ownerAlive;QString surface{"world"};
    QString root,token,instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QVariantList documents,requests,replies,inputs;QVariantMap dom;
    bool complete{true},retired{false};quint64 sequence{0};qint64 epoch{0};
    QVariantMap input,receipt,lastCommand,lastPacket;QElapsedTimer timer;
    QHash<QString,QByteArray> originalCommands;QHash<QString,QVariantMap> originalPackets;
    int worldTextAttempts{0};qint64 pointerEpoch{0};QVariantMap geometryOriginal;bool pointerIssued{false},commitIssued{false},javaReadOutstanding{false};QPointer<QTimer> focusTimer;
};
QHash<QString,WorldWebScope> worldWebScopes;
QString worldWebKey(const QVariantMap& row) {
    return row.value("handle").toString()+":"+row.value("creation").toString()+":"+row.value("grant").toString()+":"+row.value("page").toString();
}
QVariantMap worldWebPacket(const QVariantMap& command,WorldWebScope& scope,const QString& status,const QVariantMap& source={}) {
    const auto now=QDateTime::currentMSecsSinceEpoch();
    if (now<=0 || now<scope.epoch || scope.sequence>=9007199254740991ULL || !scope.complete) { return {}; }
    scope.epoch=now;
    QVariantMap packet{{"picoBrowserVersion",command.value("operation")=="commit-text" ? 4 : command.value("operation")=="measure-ray" ? 3 : 2},{"commandId",command.value("commandId")},{"runId",command.value("runId")},
        {"ownerToken",scope.token},{"instance",scope.instance},{"sequence",static_cast<qulonglong>(++scope.sequence)},
        {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",now},{"status",status},{"source",source}};
    const auto id=command.value("commandId").toString();
    scope.originalCommands.insert(id,QCryptographicHash::hash(QJsonDocument::fromVariant(command).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256));
    if (command.value("operation")=="observe") {
        for (auto it=scope.originalPackets.begin();it!=scope.originalPackets.end();) {
            if (it.value().value("source").toMap().contains("documents")) { it=scope.originalPackets.erase(it); } else { ++it; }
        }
    }
    scope.originalPackets.insert(id,packet);
    if (command.value("operation")=="input" && status!="pending") {
        for (auto& value:scope.inputs) { auto row=value.toMap();if (row.value("command").toMap().value("commandId")!=id) { continue; }
            row["completion"]=QVariantMap{{"status",status},{"capturedEpochMs",now}};value=row;break; }
    }
    if (command.value("operation")!="input") { scope.lastCommand=command;scope.lastPacket=packet; }
    return packet;
}
}
bool NativeWebViewItem::featurePicoTabletOwned(const QString& run,const QString& root) const {
    QMutexLocker guard(&_mutex);
    const auto bytes=overte::web::InlineHtmlBytes::decode(_url);
    return _surface==Tablet && bytes.valid() && _sourceIdentity.startsWith("tablet:")
        && _scriptUrl.startsWith(root+"tickets/")
        && bytes.body.contains(("<meta name=\"overte-fixture-owner\" content=\""+run+"\">").toUtf8());
}
QVariantMap NativeWebViewItem::featurePicoTabletInline() const {
    QMutexLocker guard(&_mutex);
    if (!_inlineProvided || !_inlineDocument.current()) { return {}; }
    return {{"token",_inlineDocument.token()},{"revision",static_cast<qulonglong>(_inlineDocument.revision())},
        {"transportUrl",_inlineDocument.transportURL().toString(QUrl::FullyEncoded)},
        {"sourceSha256",QString::fromLatin1(QCryptographicHash::hash(_url.toUtf8(),QCryptographicHash::Sha256).toHex())},
        {"bodySha256",QString::fromLatin1(_inlineDocument.sha256().toHex())},{"bytes",_inlineDocument.bytes().size()},
        {"charset",_inlineDocument.charset()},{"scriptUrl",_inlineDocument.scriptURL()},{"current",_inlineDocument.current()}};
}
bool NativeWebViewItem::featurePicoTabletIntercept(quint64 grant,quint64 page,const QUrl& document,const QUrl& origin,bool mainFrame,const QByteArray& payload,const QJsonObject& object) {
    if (!featureEnabled() || thread()!=QThread::currentThread() || !mainFrame || payload.isEmpty() || payload.size()>int(overte::web::EmbeddedWebSession::MAX_BRIDGE_BYTES) || !matchesOrigin(document,origin) || !allowsBridgeDocument(grant,page,document) || object.value("type")!=6
            || object.value("args").toArray().size()!=1 || !object.value("args").toArray()[0].isString()) { return false; }
    const auto message=QJsonDocument::fromJson(object.value("args").toArray()[0].toString().toUtf8());
    if (!message.isObject() || message.object().value("contract")!="overte-web-parity-v1" || message.object().value("action")!="echo") { return false; }
    for (auto scope=worldWebScopes.begin();scope!=worldWebScopes.end();++scope) {
        if (!scope->tablet || !scope->armed || scope->retired || !featurePicoTabletOwned(scope.key(),scope->root)) { continue; }
        const auto lease=featurePicoTabletInline();if (lease.isEmpty()) { scope->complete=false;return true; }
        scope->held={{"handle",QString::number(_handle)},{"creation",static_cast<qulonglong>(_creationRevision)},
            {"grant",static_cast<qulonglong>(grant)},{"page",static_cast<qulonglong>(page)},{"url",document.toString(QUrl::FullyEncoded)},
            {"origin",origin.toString(QUrl::FullyEncoded)},{"mainFrame",mainFrame},{"payloadBytes",payload.size()},
            {"token",lease.value("token")},{"revision",lease.value("revision")},{"bodySha256",lease.value("bodySha256")},
            {"sourceSha256",lease.value("sourceSha256")},
            {"payloadSha256",QString::fromLatin1(QCryptographicHash::hash(payload,QCryptographicHash::Sha256).toHex())},
            {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()}};
        QPointer<NativeWebViewItem> self(this);const auto original=_inlineDocument;
        scope->leaseCurrent=[original] { return original.current(); };scope->ownerAlive=[self] { return !self.isNull(); };
        scope->replay=[self,grant,page,document,origin,mainFrame,payload] {
            return self && self->acceptMessage(grant,page,document,origin,mainFrame,"channel",payload);
        };
        scope->heldPending=true;scope->armed=false;return true;
    }
    return false;
}
void NativeWebViewItem::featurePicoBrowserRecord(const QString& kind,const QVariant& value) {
    if (!featureEnabled() || thread()!=QThread::currentThread()) { return; }
    QString source,document;quint64 grant,page;
    { QMutexLocker guard(&_mutex);source=_session.url().toString(QUrl::FullyEncoded);document=_document.toString(QUrl::FullyEncoded);
      grant=_session.generation();page=_page; }
    for (auto scope=worldWebScopes.begin();scope!=worldWebScopes.end();++scope) {
        if ((!scope->reference && _surface!=(scope->tablet ? Tablet : WorldEntity)) || scope->retired || !(scope->reference ? source==scope->root+"index.html" : source.startsWith(scope->root+"tickets/") || (scope->tablet && featurePicoTabletOwned(scope.key(),scope->root))) || !grant || !page) { continue; }
        QVariantMap identity{{"handle",QString::number(_handle)},{"creation",static_cast<qulonglong>(_creationRevision)},
            {"grant",static_cast<qulonglong>(grant)},{"page",static_cast<qulonglong>(page)},{"url",document}};
        const auto key=worldWebKey(identity);const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<scope->epoch) { scope->complete=false;return; }
        if (kind=="documents") {
            bool found=false;
            for (const auto& row:scope->documents) { if (worldWebKey(row.toMap())==key) { found=true;break; } }
            if (found) { continue; } // Actual duplicate completion is not another load.
            if (scope->documents.size()>=256) { scope->complete=false;return; }
            identity.insert("finishedEpochMs",now);scope->documents.append(identity);
        } else if (kind=="dom") {
            const auto packet=value.toMap(),original=scope->dom.value(key).toMap();
            if (!original.isEmpty()) {
                const auto before=original.value("source").toMap().value("dom").toMap();
                const auto after=packet.value("source").toMap().value("dom").toMap();
                if (before.value("instance")!=after.value("instance")) { scope->complete=false;return; }
                for (const auto& history:QStringList{"attempts","echoes"}) {
                    const auto a=before.value(history).toList(),b=after.value(history).toList();
                    if (b.size()<a.size()) { scope->complete=false;return; }
                    for (int index=0;index<a.size();++index) { if (a[index]!=b[index]) { scope->complete=false;return; } }
                }
            }
            if (scope->dom.size()>=256 && !scope->dom.contains(key)) { scope->complete=false;return; }
            scope->dom.insert(key,packet); // Original source timestamps are preserved.
        } else if (kind=="requests" || kind=="replies") {
            if (value.userType()!=QMetaType::QString || value.toString().size()>4096) { continue; }
            const auto raw=QJsonDocument::fromJson(value.toString().toUtf8());
            if (!raw.isObject()) { continue; }const auto packet=raw.object();
            const auto sequence=packet.value("sequence").toDouble(-1);
            if (packet.value("contract")!="overte-web-parity-v1" || packet.value("action")!="echo"
                    || sequence<1 || sequence>1000000 || sequence!=int(sequence)) { continue; }
            auto& rows=kind=="requests" ? scope->requests : scope->replies;
            if (rows.size()>=128) { scope->complete=false;return; }
            identity.insert("message",value);identity.insert("capturedEpochMs",now);rows.append(identity);
        } else { scope->complete=false;return; }
    }
}
QVariantMap NativeWebViewItem::featurePicoBrowser(const QVariantMap& command) {
    if (!featureEnabled() || !overte::e2e::picoBrowserCommand(command) || !QCoreApplication::instance()
            || QThread::currentThread()!=QCoreApplication::instance()->thread()) { return {}; }
    const auto run=command.value("runId").toString(),operation=command.value("operation").toString();
    if (!worldWebScopes.contains(run)) {
        if (operation!="reserve" || worldWebScopes.size()>=32) { return {}; }
        WorldWebScope scope;scope.root=command.value("fixtureUrl").toString();scope.reference=command.value("action")=="pico-web-reference";
        scope.tablet=command.value("action")=="pico-tablet-web";
        scope.surface=scope.reference ? command.value("surface").toString() : scope.tablet ? "tablet" : "world";scope.token=command.value("ownerToken").toString();
        worldWebScopes.insert(run,scope);
    }
    auto& scope=worldWebScopes[run];
    if (scope.root!=command.value("fixtureUrl") || scope.token!=command.value("ownerToken") || !scope.complete
            || scope.reference!=(command.value("action")=="pico-web-reference") || scope.tablet!=(command.value("action")=="pico-tablet-web")
            || (scope.reference && scope.surface!=command.value("surface"))) { return {}; }
    const auto nonce=command.value("commandId").toString();
    if (scope.originalCommands.contains(nonce)) {
        if (scope.originalCommands.value(nonce)!=QCryptographicHash::hash(QJsonDocument::fromVariant(command).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256)
                || !scope.originalPackets.contains(nonce)) { return {}; }
        const auto old=scope.originalPackets.value(nonce);
        if (old.value("status")!="pending") { return old; }
        if ((operation=="input" || operation=="measure" || operation=="measure-ray" || operation=="commit-text") && scope.timer.isValid() && scope.timer.elapsed()>=4000) {
            if (scope.focusTimer) { scope.focusTimer->stop();scope.focusTimer->deleteLater(); }
            scope.receipt=worldWebPacket(command,scope,"unavailable");return scope.receipt;
        }
    } else if (scope.originalCommands.size()>=4096) { scope.complete=false;return {}; }
    if (operation!="input" && operation!="measure" && operation!="measure-ray" && operation!="commit-text" && scope.lastCommand.value("commandId")==command.value("commandId")) {
        if (scope.lastCommand!=command) { return {}; }
        if (scope.lastPacket.value("status")=="ready" || scope.lastPacket.value("status")=="unavailable") { return scope.lastPacket; }
    }
    QList<QPointer<NativeWebViewItem>> original;
    { QMutexLocker guard(&registryMutex);if (registry.size()>128) { return {}; }for (auto* item:registry) { original.append(item); } }
    QPointer<NativeWebViewItem> selected;int owned=0;
    for (const auto& item:original) {
        if (!item || item->thread()!=QThread::currentThread()) { return {}; }
        QString source;{ QMutexLocker guard(&item->_mutex);source=item->_session.url().toString(QUrl::FullyEncoded); }
        const bool matches=scope.reference ? source==scope.root+"index.html" : source.startsWith(scope.root+"tickets/") || (scope.tablet && item->featurePicoTabletOwned(run,scope.root));
        if (!matches) { continue; }++owned;
        if (item->_surface!=(scope.surface=="world" ? WorldEntity : Tablet)) { continue; }
        if (selected) { return {}; }selected=item;
    }
    if (operation=="reserve") {
        // A reservation cannot adopt an already existing owned world view.
        if (owned || scope.retired || !scope.documents.isEmpty()) { return {}; }
        return worldWebPacket(command,scope,"ready",{{"reserved",true}});
    }
    if (operation=="arm-held") {
        if (!scope.tablet || scope.retired || scope.armed || scope.heldPending || !scope.held.isEmpty() || !selected || !selected->_inlineDocument.current()) { return {}; }
        scope.armed=true;return worldWebPacket(command,scope,"ready",{{"armed",true}});
    }
    if (operation=="cancel-held") {
        if (!scope.tablet || scope.retired || !scope.armed || scope.heldPending) { return {}; }
        scope.armed=false;return worldWebPacket(command,scope,"ready",{{"cancelled",true}});
    }
    if (operation=="deliver-held") {
        if (!scope.tablet || scope.retired || !scope.heldPending || !scope.replay || scope.deliveries.size()>=16) { return {}; }
        const bool live=scope.leaseCurrent && scope.leaseCurrent(),alive=scope.ownerAlive && scope.ownerAlive();
        const bool accepted=scope.replay();auto delivery=scope.held;
        delivery.insert("deliveredEpochMs",QDateTime::currentMSecsSinceEpoch());delivery.insert("leaseCurrent",live);
        delivery.insert("ownerAlive",alive);delivery.insert("accepted",accepted);scope.deliveries.append(delivery);
        scope.heldPending=false;scope.armed=false;scope.replay={};scope.leaseCurrent={};scope.ownerAlive={};
        return worldWebPacket(command,scope,"ready",{{"delivered",true}});
    }
    if (operation=="retire") {
        if (!scope.input.isEmpty() && scope.receipt.value("status")=="pending" && scope.timer.isValid() && scope.timer.elapsed()>=4000) {
            scope.receipt=worldWebPacket(scope.input,scope,"unavailable"); // An expired input is never an effect.
        }
        if (owned || scope.armed || scope.heldPending || (!scope.input.isEmpty() && scope.receipt.value("status")=="pending")) { return {}; }
        if (scope.focusTimer || scope.javaReadOutstanding) { return {}; }scope.input.clear();scope.receipt.clear();scope.timer.invalidate();
        scope.originalPackets.clear();scope.geometryOriginal.clear();scope.retired=true;scope.held.clear();scope.deliveries.clear();scope.documents.clear();scope.requests.clear();scope.replies.clear();scope.inputs.clear();scope.dom.clear();
        return worldWebPacket(command,scope,"ready",{{"retired",true}});
    }
    if (operation=="input" || operation=="measure" || operation=="measure-ray" || operation=="commit-text") {
        if (scope.retired) { return {}; }
        if (!scope.input.isEmpty() && scope.input.value("commandId")==command.value("commandId")) {
            if (scope.input!=command) { return {}; }
            if (scope.receipt.value("status")=="pending" && scope.timer.elapsed()>=4000) { scope.receipt=worldWebPacket(command,scope,"unavailable"); }
            return scope.receipt;
        }
        if (scope.receipt.value("status")=="pending" || scope.javaReadOutstanding || scope.focusTimer || !selected) { return {}; }
        quint64 grant,page;QUrl document;
        { QMutexLocker guard(&selected->_mutex);grant=selected->_session.generation();page=selected->_page;document=selected->_document; }
        if (command.value("handle")!=QString::number(selected->_handle) || command.value("creation").toULongLong()!=selected->_creationRevision
                || command.value("grant").toULongLong()!=grant || command.value("page").toULongLong()!=page
                || !selected->allowsEditorDocument(grant,page,document) || selected->_featureWebFinishedGrant!=grant
                || selected->_featureWebFinishedPage!=page || selected->_featureWebFinishedDocument!=document) { return {}; }
        if (operation=="commit-text" && scope.worldTextAttempts++>=128) { scope.complete=false;return {}; }
        if (operation=="input" && scope.inputs.size()>=128) { scope.complete=false;return {}; }
        if (operation=="input") { scope.inputs.append(QVariantMap{{"command",command},{"issuedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"geometryRaw",QVariant()},{"focusRaw",QVariant()},{"pointerEpochMs",QVariant()},{"imeEpochMs",QVariant()},
            {"nativeBeforeIME",QVariant()},{"wheelEpochMs",QVariant()},{"completion",QVariant()}}); }
        scope.pointerEpoch=0;scope.pointerIssued=false;scope.commitIssued=false;scope.input=command;scope.timer.start();scope.receipt=worldWebPacket(command,scope,"pending");
        Jni jni;if (!jni.env) { scope.receipt=worldWebPacket(command,scope,"unavailable");return scope.receipt; }
        const auto id=jni.string(command.value("commandId").toString()),control=jni.string(command.value("control").toString());
        bool posted=false;scope.javaReadOutstanding=true;
        if (id && control) { jvalue args[5];args[0].j=selected->_handle;args[1].j=grant;args[2].j=page;args[3].l=id;args[4].l=control;
            posted=call(operation=="commit-text" ? "featurePicoFocus" : "featurePicoGeometry","(JJJLjava/lang/String;Ljava/lang/String;)V",args); }
        if (id) jni.env->DeleteLocalRef(id);if (control) jni.env->DeleteLocalRef(control);
        if (!posted) { scope.javaReadOutstanding=false;scope.receipt=worldWebPacket(command,scope,"unavailable"); }
        return scope.receipt;
    }
    QVariantMap current;
    if (selected) {
        if (scope.retired) { return {}; }
        if (scope.reference) {
            quint64 grant,page;QString source;QUrl document;bool inlineLease;
            { QMutexLocker guard(&selected->_mutex);grant=selected->_session.generation();page=selected->_page;
              document=selected->_document;source=selected->_session.url().toString(QUrl::FullyEncoded);
              inlineLease=selected->_inlineProvided && selected->_inlineDocument.current(); }
            if (!selected->allowsEditorDocument(grant,page,document) || selected->_featureWebFinishedGrant!=grant
                    || selected->_featureWebFinishedPage!=page || selected->_featureWebFinishedDocument!=document) {
                return worldWebPacket(command,scope,"pending");
            }
            QVariantMap view{{"handle",QString::number(selected->_handle)},{"creation",static_cast<qulonglong>(selected->_creationRevision)},
                {"grant",static_cast<qulonglong>(grant)},{"page",static_cast<qulonglong>(page)},{"url",document.toString(QUrl::FullyEncoded)},
                {"nativeFinished",true},{"httpErrorStatus",selected->_featureWebHTTPGrant==grant && selected->_featureWebHTTPPage==page ? selected->_featureWebHTTPStatus : 0},
                {"inlineLease",inlineLease},{"sourceUrl",source},{"sourceIdentity",selected->_sourceIdentity}};
            current={{"nativeView",view}};
        } else {
        auto request=QVariantMap{{"schemaVersion",1},{"commandId",command.value("commandId")},{"action",scope.tablet ? "feature-pico-tablet-dom-observe" : "feature-web-dom-observe"},
            {"runId",run},{"surface",scope.surface},{"fixtureUrl",scope.root}};
        const auto packet=selected->featureWebDOMRequest(request);
        if (packet.value("status")!="ready") { return worldWebPacket(command,scope,packet.value("status").toString()); }
        current=packet;
        }
    }
    QVariantMap source{{"retired",scope.retired},{"documents",scope.documents},
        {"requests",scope.requests},{"replies",scope.replies},{"inputs",scope.inputs},{"domHistory",scope.dom},{"current",current}};
    if (scope.tablet) { source.insert("deferred",QVariantMap{{"armed",scope.armed},{"pending",scope.heldPending},
        {"held",scope.held.isEmpty() ? QVariant() : QVariant(scope.held)},{"deliveries",scope.deliveries}}); }
    return worldWebPacket(command,scope,"ready",source);
}

void NativeWebViewItem::acceptFeaturePicoBrowserGeometry(qint64 handle,quint64 grant,quint64 page,
        const QString& document,const QString& request,const QByteArray& result,bool focused) {
    if (!featureEnabled() || !QCoreApplication::instance() || result.size()>16384) { return; }
    QMetaObject::invokeMethod(QCoreApplication::instance(),[handle,grant,page,document,request,result,focused] {
        QPointer<NativeWebViewItem> item;
        { QMutexLocker guard(&registryMutex);item=registry.value(handle); }
        if (item && item->thread()!=QThread::currentThread()) { return; }
        for (auto found=worldWebScopes.begin();found!=worldWebScopes.end();++found) {
            auto& scope=found.value();
            if (scope.input.value("commandId")!=request || !scope.javaReadOutstanding || focused!=(scope.input.value("operation")=="commit-text" || scope.pointerIssued)) { continue; }
            scope.javaReadOutstanding=false; // Original Java callback/UI delivery has returned, not a host timeout.
            if (scope.receipt.value("status")!="pending" || scope.retired || scope.commitIssued || scope.focusTimer) { return; }
            if (!item) { scope.receipt=worldWebPacket(scope.input,scope,"unavailable");return; }
            const auto run=found.key();const auto command=scope.input;
            const auto valid=[item,grant,page,document,command] {
                if (!item || !featureEnabled() || !item->isVisible() || !item->isEnabled()
                        || item->_presentation!=Texture
                        || item->_surface!=((command.value("operation")=="measure-ray" || command.value("operation")=="commit-text") ? WorldEntity : Tablet) || !item->window()
                        || QGuiApplication::applicationState()!=Qt::ApplicationActive
                        || !item->allowsEditorDocument(grant,page,QUrl(document))) { return false; }
                QMutexLocker guard(&item->_mutex);
                return item->current(grant,page) && item->_document.toString(QUrl::FullyEncoded)==document
                    && command.value("handle")==QString::number(item->_handle)
                    && command.value("creation").toULongLong()==item->_creationRevision
                    && command.value("grant").toULongLong()==grant && command.value("page").toULongLong()==page
                    && !item->_image.isNull();
            };
            const auto finish=[run,request](bool delivered) {
                auto found=worldWebScopes.find(run);
                if (found==worldWebScopes.end() || found->input.value("commandId")!=request
                        || found->receipt.value("status")!="pending") { return; }
                if (found->focusTimer) { found->focusTimer->stop();found->focusTimer->deleteLater(); }
                const bool timely=found->timer.isValid() && found->timer.elapsed()<4000;
                found->receipt=worldWebPacket(found->input,*found,delivered && timely ? "ready" : "unavailable",
                    delivered && timely ? QVariantMap{{"delivered",true}} : QVariantMap());
            };
            const auto quoted=QJsonDocument::fromJson('['+result+']');QVariantMap original;
            if (quoted.isArray() && quoted.array().size()==1 && quoted.array()[0].isString()) {
                const auto parsed=QJsonDocument::fromJson(quoted.array()[0].toString().toUtf8());
                if (parsed.isObject()) { original=parsed.object().toVariantMap(); }
            }
            if (command.value("operation")=="commit-text") {
                // A normal controller ray must already have focused this item.
                // This operation cannot click/focus it or replace DOM state.
                const auto point=overte::e2e::picoBrowserPoint(original,request,run,document,
                    command.value("control").toString(),QDateTime::currentMSecsSinceEpoch(),QSizeF(item->width(),item->height()));
                const auto editor=original.value("editor").toMap();
                const auto providerValue=qApp->property(overte::e2e::picoWorldWebTextProperty());
                if (!focused || !point || !valid() || scope.tablet || scope.reference || scope.surface!="world"
                        || scope.timer.elapsed()>=4000 || editor.value("focused")!=true
                        || !item->hasActiveFocus() || !item->inputMethodQuery(Qt::ImEnabled).toBool()
                        || item->_sensitive || item->_editorKind!=(command.value("control")=="foreign" ? "url" : "text")
                        || item->_surroundingStart || item->_editorText!=editor.value("text").toString()
                        || item->_cursor!=editor.value("cursor").toInt() || item->_anchor!=editor.value("anchor").toInt()
                        || providerValue.userType()!=qMetaTypeId<overte::e2e::PicoWorldWebTextProvider>()) {
                    scope.receipt=worldWebPacket(command,scope,"unavailable");return;
                }
                const auto provider=providerValue.value<overte::e2e::PicoWorldWebTextProvider>();
                if (!provider || scope.commitIssued) { scope.receipt=worldWebPacket(command,scope,"unavailable");return; }
                const QVariantMap before{{"text",item->_editorText},{"cursor",item->_cursor},{"anchor",item->_anchor},
                    {"absoluteCursor",item->_surroundingStart+item->_cursor},{"kind",item->_editorKind},
                    {"sensitive",item->_sensitive},{"focused",item->hasActiveFocus()},{"enabled",item->inputMethodQuery(Qt::ImEnabled)}};
                const QVariantMap nativeView{{"handle",QString::number(item->_handle)},{"creation",qulonglong(item->_creationRevision)},
                    {"grant",qulonglong(grant)},{"page",qulonglong(page)},{"url",document}};
                scope.commitIssued=true;const auto attempted=QDateTime::currentMSecsSinceEpoch();
                const bool delivered=provider(item,*point,command.value("text").toString(),original.value("capturedEpochMs").toLongLong());
                // A negative/late delivery keeps the same original attempted
                // event and metadata; it never becomes a DOM effect or retry.
                const bool timely=valid() && scope.timer.elapsed()<4000;
                scope.receipt=worldWebPacket(command,scope,"ready",{{"delivered",delivered && timely},
                    {"focusRaw",QString::fromUtf8(result)},{"nativeBeforeIME",before},{"imeEpochMs",attempted},
                    {"nativeView",nativeView}});return;
            }
            if (command.value("operation")=="measure-ray") {
                // A passive original, never a pointer/focus/text operation.
                // Its world geometry is produced by the scene owner from this
                // exact NativeWebViewItem and its actual QML/window transform.
                const auto point=overte::e2e::picoBrowserPoint(original,request,run,document,
                    command.value("control").toString(),QDateTime::currentMSecsSinceEpoch(),QSizeF(item->width(),item->height()));
                const auto providerValue=qApp->property(overte::e2e::picoWorldWebRayProperty());
                QVariantMap ray;
                if (!focused && point && valid() && !scope.tablet && !scope.reference && scope.surface=="world"
                        && providerValue.userType()==qMetaTypeId<overte::e2e::PicoWorldWebRayProvider>()) {
                    const auto provider=providerValue.value<overte::e2e::PicoWorldWebRayProvider>();
                    if (provider) { ray=provider(item,*point); }
                }
                const bool okay=!ray.isEmpty() && valid() && scope.timer.elapsed()<4000;
                scope.receipt=worldWebPacket(command,scope,okay ? "ready" : "unavailable",
                    okay ? QVariantMap{{"geometryRaw",QString::fromUtf8(result)},{"worldRay",ray},
                        {"nativeView",QVariantMap{{"handle",QString::number(item->_handle)},{"creation",qulonglong(item->_creationRevision)},
                            {"grant",qulonglong(grant)},{"page",qulonglong(page)},{"url",document}}}} : QVariantMap());return;
            }
            if (command.value("operation")=="measure") {
                // Preserve the original read even when the control is offscreen.
                // The consumer validates its closed DOM schema independently.
                const bool okay=!focused && valid() && !original.isEmpty() && scope.timer.elapsed()<4000;
                scope.receipt=worldWebPacket(command,scope,okay ? "ready" : "unavailable",
                    okay ? QVariantMap{{"geometryRaw",QString::fromUtf8(result)},
                        {"nativeView",QVariantMap{{"handle",QString::number(item->_handle)},{"creation",qulonglong(item->_creationRevision)},
                            {"grant",qulonglong(grant)},{"page",qulonglong(page)},{"url",document}}}} : QVariantMap());return;
            }
            for (auto& value:scope.inputs) { auto row=value.toMap();if (row.value("command").toMap().value("commandId")!=request) { continue; }
                row[focused ? "focusRaw" : "geometryRaw"]=QString::fromUtf8(result);value=row;break; }
            const auto point=overte::e2e::picoBrowserPoint(original,request,run,document,
                command.value("control").toString(),QDateTime::currentMSecsSinceEpoch(),QSizeF(item->width(),item->height()));
            const auto providerValue=qApp->property(overte::e2e::picoBrowserInputProperty());
            if (!point || !valid() || scope.timer.elapsed()>=4000
                    || providerValue.userType()!=qMetaTypeId<overte::e2e::PicoBrowserInputProvider>()) { finish(false);return; }
            const auto provider=providerValue.value<overte::e2e::PicoBrowserInputProvider>();
            const auto view=original.value("viewport").toMap();
            { QMutexLocker guard(&item->_mutex);
              if (std::abs(double(item->_image.width())/item->_image.height()
                      -view.value("width").toDouble()/view.value("height").toDouble())>0.02) { guard.unlock();finish(false);return; } }
            const auto control=command.value("control").toString();
            if (!focused && (control=="scroll-up" || control=="scroll-down")) {
                const auto attempted=QDateTime::currentMSecsSinceEpoch();
                for (auto& value:scope.inputs) { auto row=value.toMap();if (row.value("command").toMap().value("commandId")!=request) { continue; }
                    row["wheelEpochMs"]=attempted;value=row;break; }
                finish(provider.scroll && provider.scroll(item,*point,control=="scroll-up" ? 120 : -120,
                    original.value("capturedEpochMs").toLongLong()));return;
            }
            if (!focused) {
                scope.pointerIssued=true;scope.pointerEpoch=QDateTime::currentMSecsSinceEpoch();scope.geometryOriginal=original;
                for (auto& value:scope.inputs) { auto row=value.toMap();if (row.value("command").toMap().value("commandId")!=request) { continue; }
                    row["pointerEpochMs"]=scope.pointerEpoch;value=row;break; }
                if (!provider.pointer || !provider.pointer(item,*point,original.value("capturedEpochMs").toLongLong())) { finish(false);return; }
                if (control!="text" && control!="foreign") { finish(true);return; }
                Jni jni;if (!jni.env) { finish(false);return; }
                const auto id=jni.string(request),field=jni.string(control);bool posted=false;scope.javaReadOutstanding=true;
                if (id && field) { jvalue args[5];args[0].j=handle;args[1].j=grant;args[2].j=page;args[3].l=id;args[4].l=field;
                    posted=call("featurePicoFocus","(JJJLjava/lang/String;Ljava/lang/String;)V",args); }
                if (id) jni.env->DeleteLocalRef(id);if (field) jni.env->DeleteLocalRef(field);
                if (!posted) { scope.javaReadOutstanding=false;finish(false); }return;
            }
            const auto editor=original.value("editor").toMap();
            if (!valid() || !provider.text || editor.value("focused")!=true
                    || scope.geometryOriginal.value("instance")!=original.value("instance")
                    || scope.geometryOriginal.value("sequence").toULongLong()>=original.value("sequence").toULongLong()
                    || scope.geometryOriginal.value("capturedEpochMs").toLongLong()>original.value("capturedEpochMs").toLongLong()
                    || original.value("capturedEpochMs").toLongLong()<scope.pointerEpoch) { finish(false);return; }
            // One pointer, one IME event. Wait only for independently delivered
            // native editor metadata matching the fresh focused original DOM.
            auto* timer=new QTimer(qApp);scope.focusTimer=timer;timer->setInterval(20);
            QObject::connect(timer,&QTimer::timeout,timer,[run,request,item,valid,finish,provider,command,editor,original] {
                auto found=worldWebScopes.find(run);
                if (found==worldWebScopes.end() || found->input.value("commandId")!=request
                        || found->receipt.value("status")!="pending") { return; }
                const auto now=QDateTime::currentMSecsSinceEpoch();
                if (!valid() || found->timer.elapsed()>=4000 || now<original.value("capturedEpochMs").toLongLong()
                        || now-original.value("capturedEpochMs").toLongLong()>1500) { finish(false);return; }
                if (!item->hasActiveFocus() || !item->inputMethodQuery(Qt::ImEnabled).toBool()
                        || item->_sensitive || item->_editorKind!=(command.value("control")=="foreign" ? "url" : "text")
                        || item->_surroundingStart || item->_editorText!=editor.value("text").toString()
                        || item->_cursor!=editor.value("cursor").toInt() || item->_anchor!=editor.value("anchor").toInt()) { return; }
                if (found->commitIssued) { finish(false);return; }
                found->commitIssued=true;
                for (auto& value:found->inputs) { auto row=value.toMap();if (row.value("command").toMap().value("commandId")!=request) { continue; }
                    row["imeEpochMs"]=QDateTime::currentMSecsSinceEpoch();
                    row["nativeBeforeIME"]=QVariantMap{{"text",item->_editorText},{"cursor",item->_cursor},{"anchor",item->_anchor},
                        {"absoluteCursor",item->_surroundingStart+item->_cursor},{"kind",item->_editorKind},{"sensitive",item->_sensitive},
                        {"focused",item->hasActiveFocus()},{"enabled",item->inputMethodQuery(Qt::ImEnabled)}};value=row;break; }
                finish(provider.text(item,command.value("text").toString(),original.value("capturedEpochMs").toLongLong()));
            });
            timer->start();return;
        }
    },Qt::QueuedConnection);
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeFeaturePicoGeometry(JNIEnv* env,jclass,
        jlong handle,jlong grant,jlong page,jstring document,jstring request,jstring result) {
    if (!document || !request || !result || env->GetStringLength(document)>131072
            || env->GetStringLength(request)!=32 || env->GetStringLength(result)>16384) { return; }
    NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,page,string(env,document),string(env,request),string(env,result).toUtf8());
}
extern "C" JNIEXPORT void JNICALL Java_org_overte_web_EmbeddedWebView_nativeFeaturePicoFocus(JNIEnv* env,jclass,
        jlong handle,jlong grant,jlong page,jstring document,jstring request,jstring result) {
    if (!document || !request || !result || env->GetStringLength(document)>131072
            || env->GetStringLength(request)!=32 || env->GetStringLength(result)>16384) { return; }
    NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,page,string(env,document),string(env,request),string(env,result).toUtf8(),true);
}
#else
#if defined(OVERTE_E2E_FEATURE_TESTS)
QVariantMap NativeWebViewItem::featurePicoBrowser(const QVariantMap&) { return {}; }
void NativeWebViewItem::acceptFeaturePicoBrowserGeometry(qint64,quint64,quint64,const QString&,const QString&,const QByteArray&,bool) {}
void NativeWebViewItem::featurePicoBrowserRecord(const QString&,const QVariant&) {}
bool NativeWebViewItem::featurePicoTabletOwned(const QString&,const QString&) const { return false; }
bool NativeWebViewItem::featurePicoTabletIntercept(quint64,quint64,const QUrl&,const QUrl&,bool,const QByteArray&,const QJsonObject&) { return false; }
QVariantMap NativeWebViewItem::featurePicoTabletInline() const { return {}; }
#endif
#endif
