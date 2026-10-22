// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include "NormalScriptFileControls.h"
#include "ScriptUiInventory.h"
#include "NormalAudioControls.h"
#include "NormalGraphicsControls.h"
#include "NormalLoginControls.h"
#include "NormalCreateControls.h"
#include "NormalCreateExtraControls.h"
#include "NormalCreateVoxelControls.h"
#include "NormalChatControls.h"
#include <ui/NativeFieldInput.h>
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QGuiApplication>
#include <QHash>
#include <QKeyEvent>
#include <QPointer>
#include <QQuickWindow>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <algorithm>
#include <cmath>
#include <functional>

namespace overte::e2e {
#if defined(OVERTE_E2E_FEATURE_TESTS)
class NormalControlUi {
public:
    enum class Surface { ScriptFiles, Audio, Graphics, Login, Create, CreateExtra, CreateVoxel, Chat };
    explicit NormalControlUi(Surface surface = Surface::ScriptFiles) : _surface(surface), _instance(nonce()), _generation(nonce()) { _clock.start(); }

    QJsonObject observe(QQuickItem* root, QQuickWindow* window, const AudioUiContext& audio = {}, const GraphicsUiContext& graphics = {}, const LoginUiContext& login = {}) {
        if (!qApp || QThread::currentThread() != qApp->thread()
                || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        if (_root != root || _window != window) {
            _root = root; _window = window; _generation = nonce(); _controls.clear();
        }
        bool ready = root && window && root->window() == window
            && root->thread() == qApp->thread() && window->thread() == qApp->thread()
            && (_surface != Surface::Audio || audio.valid) && (_surface != Surface::Graphics || graphics.valid)
            && (_surface != Surface::Login || login.valid);
        QHash<QString, Control> controls;
        int visited {0};
        bool ambiguous {false};
        ScriptUiInventory scriptInventory;
        std::function<void(QQuickItem*, int)> walk = [&](QQuickItem* item, int depth) {
            if (!item || ambiguous) { return; }
            if (++visited > 4096 || depth > 128 || item->thread() != qApp->thread()) { ambiguous = true; return; }
            if (_surface==Surface::ScriptFiles) { scriptInventory.visit(item); }
            if (_surface == Surface::Graphics ? graphicsObservable(item) : !visibleRect(item, window).isEmpty()) {
                const auto id = _surface == Surface::Audio ? audioControlId(item)
                    : _surface == Surface::Graphics ? graphicsControlId(item)
                    : _surface == Surface::Login ? loginControlId(item)
                    : _surface == Surface::Create ? createControlId(item)
                    : _surface == Surface::CreateExtra ? createExtraControlId(item)
                    : _surface == Surface::CreateVoxel ? createVoxelControlId(item)
                    : _surface == Surface::Chat ? chatControlId(item) : scriptFileControlId(item);
                if (!id.isEmpty()) {
                    if (controls.contains(id)) { ambiguous = true; return; }
                    const auto previous = _controls.value(id);
                    const auto source = _surface == Surface::Audio ? audioControlSource(item, id, audio)
                        : _surface == Surface::Graphics ? graphicsControlSource(item, id, graphics)
                        : _surface == Surface::Login ? loginControlSource(item, id, login)
                        : _surface == Surface::Create ? createControlSource(item,id)
                        : _surface == Surface::CreateExtra ? createExtraControlSource(item,id)
                        : _surface == Surface::CreateVoxel ? createVoxelControlSource(item,id)
                        : _surface == Surface::Chat ? chatControlSource(item,id) : scriptFileControlSource(item);
                    if ((_surface==Surface::Chat || _surface==Surface::CreateExtra || _surface==Surface::CreateVoxel) && source.isEmpty()) { ambiguous=true;return; }
                    controls.insert(id, {item, previous.item == item && previous.source == source ? previous.token : nonce(), source});
                }
            }
            for (auto child : item->childItems()) { walk(child, depth + 1); }
        };
        if (ready) {
            walk(root, 0);
            if (root->parentItem() == window->contentItem()) {
                for (auto layer : window->contentItem()->childItems()) {
                    if (layer != root && layer->inherits("QQuickOverlay")) { walk(layer, 0); }
                }
            }
        }
        bool picker {false};
        for (const auto& id : controls.keys()) { picker = picker || id.startsWith(QStringLiteral("script-file.")); }
        if (picker) { controls.remove(QStringLiteral("scripts.from-file")); }
        if (ambiguous || controls.size() > 384) { ready = false; controls.clear(); }
        _controls = controls;
        auto ids = controls.keys(); std::sort(ids.begin(), ids.end());
        QJsonArray rows;
        for (const auto& id : ids) {
            const auto control = controls.value(id);
            QJsonObject row{{"id", id}, {"token", control.token}, {"enabled", control.item->isEnabled()},
                {"focused", control.item->hasActiveFocus()}};
            if (_surface == Surface::Audio) { appendAudioControlObservation(row, control.item, id, audio); }
            else if (_surface == Surface::Graphics) { appendGraphicsControlObservation(row, control.item, id, graphics); }
            else if (_surface == Surface::Login) { appendLoginControlObservation(row, control.item, id, login); }
            else if (_surface == Surface::Create) { appendCreateControlObservation(row,control.item,id); }
            else if (_surface == Surface::CreateExtra) { appendCreateExtraObservation(row,control.item,id); }
            else if (_surface == Surface::CreateVoxel) { appendCreateVoxelObservation(row,control.item,id); }
            else if (_surface == Surface::Chat) { appendChatControlObservation(row,control.item,id); }
            else { appendScriptFileObservation(row, control.item, id); }
            rows.append(row);
        }
        QJsonObject result{{"schemaVersion", 1}, {"instance", _instance}, {"generation", _generation},
            {"sourceSequence", static_cast<double>(++_sourceSequence)},
            {"lastCommandSequence", static_cast<double>(_lastCommandSequence)}, {"elapsedMs", static_cast<double>(_clock.elapsed())},
            {"capturedEpochMs", static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
            {"processId", static_cast<double>(QCoreApplication::applicationPid())},
            {"ready", ready}, {"controls", rows}};
        result[_surface == Surface::Audio ? "audioControlsVersion"
            : _surface == Surface::Graphics ? "graphicsControlsVersion"
            : _surface == Surface::Login ? "loginControlsVersion"
            : _surface == Surface::Create ? "createControlsVersion"
            : _surface == Surface::CreateExtra ? "createExtraControlsVersion"
            : _surface == Surface::CreateVoxel ? "createVoxelControlsVersion"
            : _surface == Surface::Chat ? "chatControlsVersion" : "fileControlsVersion"] = _surface==Surface::Login ? 2 : 1;
        if (_surface==Surface::CreateExtra) {result["createExtraUiInventory"]=createExtraUiLifetimes().snapshot();}
        if (_surface==Surface::ScriptFiles) { result["scriptInventory"]=scriptInventory.observation(ready); }
        return result;
    }

    QJsonObject apply(QQuickItem* root, QQuickWindow* window, const QJsonObject& command,
                      const std::function<bool(QQuickItem*)>& pointerClick, const AudioUiContext& audio = {},
                      const std::function<bool(QQuickItem*, const QPointF&)>& pointerAt = {},
                      const GraphicsUiContext& graphics = {}, const LoginUiContext& login = {}) {
        if (!qApp || QThread::currentThread() != qApp->thread()
                || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        const auto current = observe(root, window, audio, graphics, login);
        const auto request = command.value("commandId").toString();
        QJsonObject result{{"schemaVersion", 1}, {"commandId", request}, {"performed", false},
            {"instance", _instance}, {"generation", _generation}, {"sequence", command.value("sequence")},
            {"processId", static_cast<double>(QCoreApplication::applicationPid())}};
        const auto action = command.value("action").toString();
        QSet<QString> fields{"schemaVersion", "commandId", "instance", "generation", "sequence", "observedElapsedMs",
            "controlId", "controlToken", "action"};
        if (action == "replace") { fields.insert("text"); }
        if (action == "select-index") { fields.insert("index"); }
        if (action == "scroll") { fields.insert("direction"); }
        if (action == "set-value") { fields.insert("value"); }
        const auto keys = command.keys();
        qint64 sequence {0}, observed {0};
        if (!current.value("ready").toBool() || QSet<QString>(keys.begin(), keys.end()) != fields
                || command.value("schemaVersion") != QJsonValue(1)
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(request).hasMatch()
                || command.value("instance") != QJsonValue(_instance) || command.value("generation") != QJsonValue(_generation)
                || !integer(command.value("sequence"), sequence) || sequence != _lastCommandSequence + 1
                || !integer(command.value("observedElapsedMs"), observed) || observed > _clock.elapsed()
                || _clock.elapsed() - observed > 5000
                || (_surface == Surface::Audio ? action != "activate" && action != "scroll"
                    : _surface == Surface::Graphics ? action != "activate" && action != "scroll" && action != "set-value"
                    : _surface == Surface::Login ? action != "activate" && action != "replace" && action != "submit"
                    : _surface == Surface::CreateExtra ? action != "activate" && action != "replace" && action != "select-index"
                    : _surface == Surface::CreateVoxel ? action != "activate" && action != "replace" && action != "select-index"
                    : _surface == Surface::Create ? action != "activate" && action != "replace" && action != "select-index" && action != "scroll"
                    : _surface == Surface::Chat ? action != "activate" && action != "replace" && action != "submit"
                    : action != "activate" && action != "replace" && action != "submit" && action != "select-index")) { return result; }
        // Consume intent before dispatch; never replay uncertain native input.
        _lastCommandSequence = sequence;
        const auto id = command.value("controlId").toString();
        const auto control = _controls.value(id);
        if (!control.item || !control.item->isEnabled() || command.value("controlToken") != QJsonValue(control.token)
                || visibleRect(control.item, window).isEmpty()) { return result; }
        bool delivered {false};
        if (_surface == Surface::Chat) {
            QJsonObject row;appendChatControlObservation(row,control.item,id);
            if (!row.value("inputReady").toBool()) { return result; }
            const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
            if (action=="activate" && id!="chat.page" && pointerClick && ownsPoint(control.item,window,point)) {
                delivered=pointerClick(control.item);
            } else if (id=="chat.input" && action=="replace" && command.value("text").isString()
                    && chatText(command.value("text").toString()) && ownsPoint(control.item,window,point)) {
                delivered=overte::ui::replaceFocusedField(control.item,window,command.value("text").toString());
            } else if (id=="chat.input" && action=="submit") {
                delivered=overte::ui::submitFocusedField(control.item,window);
            }
        } else if (_surface == Surface::Create) {
            QJsonObject row;appendCreateControlObservation(row,control.item,id);
            const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
            if (!row.value("inputReady").toBool()) { return result; }
            if (action=="scroll" && id=="create.scrollbar") {
                QPointF scrollPoint;
                if (createScrollPoint(control.item,command.value("direction").toString(),scrollPoint)
                        && ownsPoint(control.item,window,scrollPoint) && pointerAt) { delivered=pointerAt(control.item,scrollPoint); }
            } else if (action=="activate" && id!="create.page" && id!="create.scrollbar" && pointerClick
                    && ownsPoint(control.item,window,point)) { delivered=pointerClick(control.item); }
            else if (action=="replace" && createField(id) && command.value("text").isString()
                    && createText(command.value("text").toString()) && ownsPoint(control.item,window,point)) {
                delivered=overte::ui::replaceFocusedField(control.item,window,command.value("text").toString());
            } else if (action=="select-index" && createChoice(id)) {
                qint64 index {0};
                if (integer(command.value("index"),index)) { delivered=selectCreateChoice(control.item,window,index); }
            }
        } else if (_surface == Surface::CreateExtra) {
            QJsonObject row;appendCreateExtraObservation(row,control.item,id);
            const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
            if (!row.value("inputReady").toBool()) { return result; }
            const auto own=[&]{return ownsPoint(control.item,window,point,createExtraDecoration);};
            if (action=="activate" && id!="create-extra.polyvox.page" && pointerClick && own()) { delivered=pointerClick(control.item); }
            else if (action=="replace" && command.value("text").isString() && createExtraText(id,command.value("text").toString()) && own()) {
                delivered=overte::ui::replaceFocusedField(control.item,window,command.value("text").toString());
            } else if (action=="select-index" && createExtraCount(id)) {
                qint64 index{0};if (integer(command.value("index"),index)) { delivered=selectCreateChoice(control.item,window,index,createExtraCount(id)); }
            }
        } else if (_surface == Surface::CreateVoxel) {
            QJsonObject row;appendCreateVoxelObservation(row,control.item,id);
            const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
            if (!row.value("inputReady").toBool()) {return result;}
            if (action=="activate" && pointerClick && ownsPoint(control.item,window,point)) {delivered=pointerClick(control.item);}
            else if (action=="replace" && command.value("text").isString()
                    && createVoxelText(id,command.value("text").toString()) && ownsPoint(control.item,window,point)) {
                delivered=overte::ui::replaceFocusedField(control.item,window,command.value("text").toString());
            } else if (action=="select-index" && createVoxelCount(id)) {
                qint64 index{0};if (integer(command.value("index"),index)) {delivered=selectCreateChoice(control.item,window,index,createVoxelCount(id));}
            }
        } else if (_surface == Surface::Login) {
            QJsonObject row;
            appendLoginControlObservation(row,control.item,id,login);
            if (!row.value("inputReady").toBool()) { return result; }
            if (action == "activate" && id != "login.page") {
                const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
                if (ownsPoint(control.item,window,point) && pointerClick) { delivered=pointerClick(control.item); }
            } else if ((id=="login.username" || id=="login.password" || id=="login.server") && action=="replace"
                    && command.value("text").isString() && validLoginText(command.value("text").toString())) {
                delivered=overte::ui::replaceFocusedField(control.item,window,command.value("text").toString());
            } else if (id=="login.password" && action=="submit") {
                delivered=overte::ui::submitFocusedField(control.item,window);
            }
        } else if (_surface == Surface::Graphics) {
            QJsonObject row;
            appendGraphicsControlObservation(row, control.item, id, graphics);
            if (!row.value("inputReady").toBool()) { return result; }
            QPointF point;
            if (action == "set-value" && id == "graphics.resolution" && command.value("value").isDouble()) {
                if (graphicsSliderPoint(control.item,command.value("value").toDouble(),point)
                        && ownsPoint(control.item,window,point) && pointerAt) { delivered = pointerAt(control.item,point); }
            } else if (action == "scroll" && id == "graphics.scrollbar") {
                if (graphicsScrollPoint(control.item,command.value("direction").toString(),point)
                        && ownsPoint(control.item,window,point) && pointerAt) { delivered = pointerAt(control.item,point); }
            } else if (action == "activate" && id != "graphics.page" && id != "graphics.scrollbar" && id != "graphics.resolution") {
                point = control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
                if (ownsPoint(control.item,window,point) && pointerClick) { delivered = pointerClick(control.item); }
            }
        } else if (_surface == Surface::Audio) {
            QJsonObject row;
            appendAudioControlObservation(row, control.item, id, audio);
            if (!row.value("inputReady").toBool()) { return result; }
            if (action == "scroll" && id == "audio.scrollbar") {
                QPointF point;
                if (audioScrollPoint(control.item, command.value("direction").toString(), point)
                        && ownsPoint(control.item, window, point) && pointerAt) { delivered = pointerAt(control.item, point); }
            } else if (action == "activate" && id != "audio.scrollbar" && id != "audio.page") {
                const auto point = control.item->mapToScene(QPointF(control.item->width()/2, control.item->height()/2));
                if (ownsPoint(control.item, window, point) && pointerClick) { delivered = pointerClick(control.item); }
            }
        } else if (action == "activate") {
            delivered = pointerClick && pointerClick(control.item);
        } else if (id == QStringLiteral("script-file.folder")) {
            if (action == "replace" && command.value("text").isString()) {
                const auto text = command.value("text").toString();
                if (validScriptFolderPath(text)) {
                    delivered = overte::ui::replaceFocusedField(control.item, window, text);
                }
            } else if (action == "submit") { delivered = overte::ui::submitFocusedField(control.item, window); }
        } else if (id == QStringLiteral("script-file.primary") && action == "select-index") {
            qint64 index {0};
            if (integer(command.value("index"), index)) { delivered = selectFocusedPrimary(control.item, window, index); }
        }
        result["performed"] = delivered; // Input delivery only; read real state separately.
        return result;
    }

    static QRectF visibleRect(QQuickItem* item, QQuickWindow* window) {
        if (!item || !window || window->thread() != QThread::currentThread()
                || item->thread() != QThread::currentThread()
                || item->window() != window || item->width() <= 0 || item->height() <= 0) { return {}; }
        auto rect = item->mapRectToScene(QRectF(0, 0, item->width(), item->height()));
        const auto center = item->mapToScene(QPointF(item->width() / 2, item->height() / 2));
        if (!std::isfinite(rect.x()) || !std::isfinite(rect.y()) || !std::isfinite(rect.width())
                || !std::isfinite(rect.height()) || !std::isfinite(center.x()) || !std::isfinite(center.y())) { return {}; }
        rect = rect.intersected(QRectF(0, 0, window->width(), window->height()));
        for (auto parent = item; parent; parent = parent->parentItem()) {
            if (!parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity() <= 0.01) { return {}; }
            if (parent->clip()) { rect = rect.intersected(parent->mapRectToScene(parent->clipRect())); }
        }
        return rect.contains(center) ? rect : QRectF();
    }

    static bool selectFocusedPrimary(QQuickItem* item, QQuickWindow* window, qint64 index) {
        if (!item || !window || !qApp || QThread::currentThread() != qApp->thread()
                || item->thread() != QThread::currentThread() || window->thread() != QThread::currentThread()
                || !QCoreApplication::arguments().contains("--testScript")
                || scriptFileControlId(item) != QStringLiteral("script-file.primary")
                || visibleRect(item, window).isEmpty() || !item->isEnabled()
                || index < 0 || index >= 32 || index >= item->property("count").toInt() || !ownsFocus(item, window)) { return false; }
        QPointer<QQuickItem> original = item;
        QPointer<QQuickWindow> surface = window;
        bool delivered = key(surface, Qt::Key_Home);
        for (int step = 0; delivered && original && surface && step < index; ++step) {
            delivered = ownsFocus(original, surface) && key(surface, Qt::Key_Down);
        }
        return delivered && original && surface && ownsFocus(original, surface) && key(surface, Qt::Key_Return);
    }

    static bool selectCreateChoice(QQuickItem* item,QQuickWindow* window,qint64 index,int extraCount=0) {
        if (!item || !window || visibleRect(item,window).isEmpty() || !item->isEnabled()
                || (extraCount ? (createExtraCount(createExtraControlId(item))!=extraCount && createVoxelCount(createVoxelControlId(item))!=extraCount) || item->property("count").toInt()!=extraCount
                    : !createChoice(createControlId(item))) || !item->inherits("QQuickComboBox")
                || index<0 || index>=32 || index>=item->property("count").toInt()) { return false; }
        const auto focused=[&] {
            if (!extraCount && ownsFocus(item,window)) {return true;}
            auto popup=item->property("popup").value<QObject*>();
            auto content=popup ? qobject_cast<QQuickItem*>(popup->property("contentItem").value<QObject*>()) : nullptr;
            const bool shown=popup && popup->property("visible").toBool();
            bool actualFocus=ownsFocus(item,window);
            if (shown && content && content->window()==window) {
                for (auto focus=window->activeFocusItem();focus;focus=focus->parentItem()) {if (focus==content) {actualFocus=true;}}
            }
            if (!actualFocus) {return false;}
            if (!extraCount) {return true;}
            // The original Qt Combo can keep focus while its real popup is
            // open. Hit its actual content rather than the covered combo.
            if (shown) {
                return content && content->window()==window && ownsPoint(content,window,
                    content->mapToScene(QPointF(content->width()/2,content->height()/2)));
            }
            return ownsPoint(item,window,item->mapToScene(QPointF(item->width()/2,item->height()/2)),createExtraDecoration);
        };
        if (!focused()) { return false; }
        QPointer<QQuickItem> original=item;QPointer<QQuickWindow> surface=window;
        bool delivered=key(window,Qt::Key_Home);
        for (int step=0;delivered && original && surface && step<index;++step) {
            delivered=focused() && key(surface,Qt::Key_Down);
        }
        return delivered && original && surface && focused() && key(surface,Qt::Key_Return);
    }

    // Conservative actual scene hit-test: an overlay/modal outside the
    // resolved item blocks input. Never replace the point by guessed coordinates.
    static bool ownsPoint(QQuickItem* item, QQuickWindow* window, const QPointF& point,
                          const std::function<bool(QQuickItem*,QQuickItem*)>& decoration = std::function<bool(QQuickItem*,QQuickItem*)>()) {
        const auto visible=visibleRect(item,window);
        if (visible.isEmpty() || !item->isEnabled() || !visible.contains(point)) { return false; }
        int visited{0};bool complete{true};
        std::function<QQuickItem*(QQuickItem*,int)> top=[&](QQuickItem* node,int depth)->QQuickItem* {
            if (!node || !complete) { return nullptr; }
            if (++visited>4096 || depth>128 || node->thread()!=QThread::currentThread()) { complete=false;return nullptr; }
            if (!node->isVisible()) { return nullptr; }
            const auto opacity=node->opacity(),z=node->z();
            const auto local=node->mapFromScene(point);
            if (!std::isfinite(opacity) || !std::isfinite(z) || !std::isfinite(local.x()) || !std::isfinite(local.y())
                    || !std::isfinite(node->width()) || !std::isfinite(node->height())) {
                complete=false;return nullptr;
            }
            if (node->clip()) {
                const auto clip=node->clipRect();
                if (!std::isfinite(clip.x()) || !std::isfinite(clip.y()) || !std::isfinite(clip.width()) || !std::isfinite(clip.height())) {
                    complete=false;return nullptr;
                }
                if (!clip.contains(local)) { return nullptr; }
            }
            if (opacity<=.01) { return nullptr; }
            // Non-clipping Flickable content items can have zero geometry while
            // their original Layout/TextInput children paint and accept input
            // outside it. Do not stop at that container's contains() result.
            // Preserve actual visual z order, foreign occlusion and all clips.
            auto children=node->childItems();
            for (auto child:children) { if (!std::isfinite(child->z())) { complete=false;return nullptr; } }
            std::stable_sort(children.begin(),children.end(),[](QQuickItem* a,QQuickItem* b) { return a->z()<b->z(); });
            for (auto child=children.crbegin();child!=children.crend();++child) {
                if ((*child)->z()<0) { continue; }
                const auto found=top(*child,depth+1);if (!complete || found) { return found; }
            }
            // Negative-z children paint behind their parent's own content.
            // Without pixel-level transparency proof, its geometry conservatively
            // blocks an underlying child. Outside a non-clipping parent, that
            // child may still be the actual highest painted/interactive item.
            if (node->contains(local) && (!decoration || !decoration(node,item))) { return node; }
            for (auto child=children.crbegin();child!=children.crend();++child) {
                if ((*child)->z()>=0) { continue; }
                const auto found=top(*child,depth+1);if (!complete || found) { return found; }
            }
            return nullptr;
        };
        const auto hit=top(window->contentItem(),0);if (!complete) { return false; }
        for (auto parent=hit;parent;parent=parent->parentItem()) { if (parent==item) { return true; } }
        return false;
    }

private:
    Surface _surface;
    struct Control { QPointer<QQuickItem> item; QString token, source; };
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool integer(const QJsonValue& value, qint64& number) {
        const auto candidate = value.toDouble(-1);
        if (!value.isDouble() || !std::isfinite(candidate) || candidate < 0 || candidate > 9007199254740991.0
                || std::floor(candidate) != candidate) { return false; }
        number = static_cast<qint64>(candidate); return true;
    }
    static bool ownsFocus(QQuickItem* item, QQuickWindow* window) {
        if (!item || !window || !window->activeFocusItem()) { return false; }
        for (auto focus = static_cast<QObject*>(window->activeFocusItem()); focus; focus = focus->parent()) {
            if (focus == item) { return true; }
        }
        return false;
    }
    static bool key(QQuickWindow* window, int code) {
        if (!window) { return false; }
        QPointer<QQuickWindow> guarded = window;
        QKeyEvent press(QEvent::KeyPress, code, Qt::NoModifier);
        const bool delivered = QCoreApplication::sendEvent(window, &press);
        if (guarded) {
            QKeyEvent release(QEvent::KeyRelease, code, Qt::NoModifier);
            QCoreApplication::sendEvent(guarded, &release);
        }
        return delivered;
    }
    QPointer<QQuickItem> _root;
    QPointer<QQuickWindow> _window;
    QHash<QString, Control> _controls;
    QString _instance, _generation;
    QElapsedTimer _clock;
    quint64 _sourceSequence {0};
    qint64 _lastCommandSequence {0};
};
class ScriptFileUi : public NormalControlUi {};
class GraphicsUi : public NormalControlUi {
public:
    GraphicsUi() : NormalControlUi(Surface::Graphics) {}
};
class CreateUi : public NormalControlUi {
public:
    CreateUi() : NormalControlUi(Surface::Create) {}
};
class ChatUi : public NormalControlUi {
public:
    ChatUi() : NormalControlUi(Surface::Chat) {}
};
class LoginUi : public NormalControlUi {
public:
    LoginUi() : NormalControlUi(Surface::Login) {}
};
class AudioUi : public NormalControlUi {
public:
    AudioUi() : NormalControlUi(Surface::Audio) {}
};
#endif
} // namespace overte::e2e
