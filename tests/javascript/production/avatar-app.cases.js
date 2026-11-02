"use strict";
// SPDX-License-Identifier: Apache-2.0
// Execute the complete shipped app; the tablet, avatar and entity APIs are boundaries.
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");
const { createScriptApi, createTabletApi, FakeSignal, runProductionScript } = require("../support");

const source = path.resolve(__dirname, "../../../scripts/system/avatarapp.js");

function start(touch) {
    const Script = createScriptApi();
    Script.include = () => {};
    Script.resolvePath = value => "packaged:" + value;
    const Tablet = createTabletApi();
    const calls = [];
    const signal = () => new FakeSignal();
    const MyAvatar = {
        sessionUUID: "self", SELF_ID: "self-id", skeletonModelURL: "https://example.invalid/original.fst",
        getAvatarEntitiesVariant: () => [], getAvatarScale: () => 1,
        getDominantHand: () => "right", getHmdAvatarAlignmentType: () => 0,
        getCollisionsEnabled: () => true, getOtherAvatarsCollisionsEnabled: () => true,
        getAnimGraphUrl: () => "", getAnimGraphOverrideUrl: () => "", getJointNames: () => ["Hips"],
        getFullAvatarURLFromPreferences: () => "https://example.invalid/original.fst",
        useFullAvatarURL: value => calls.push(["avatar", value]),
        setAvatarScale: value => calls.push(["scale", value])
    };
    ["skeletonModelURLChanged", "dominantHandChanged", "hmdAvatarAlignmentTypeChanged",
        "collisionsEnabledChanged", "otherAvatarsCollisionsEnabledChanged", "newCollisionSoundURL",
        "animGraphUrlChanged", "targetScaleChanged"].forEach(key => { MyAvatar[key] = signal(); });
    const AvatarBookmarks = {
        bookmarkLoaded: signal(), bookmarkDeleted: signal(), bookmarkAdded: signal(),
        getBookmarks: () => ({ saved: {} }), getBookmark: name => name === "saved" ? {} : null,
        loadBookmark: name => calls.push(["bookmark", name]),
        addBookmark: name => calls.push(["addBookmark", name]),
        removeBookmark: name => calls.push(["removeBookmark", name])
    };
    const Entities = {
        addingWearable: signal(), deletingWearable: signal(), mousePressOnEntity: signal(),
        getEntityProperties: () => ({ parentID: "self" }),
        editEntity: (id, props) => calls.push(["edit", id, props]),
        addEntity: (props, avatar) => { calls.push(["wearable", props, avatar]); return "wearable-id"; },
        deleteEntity: id => calls.push(["delete", id])
    };
    runProductionScript(source, {
        ANDROID_PHONE_INTERFACE: touch, Script, Tablet, MyAvatar, AvatarBookmarks, Entities,
        Quat: { fromVec3Degrees: value => value, safeEulerAngles: value => value },
        Camera: { mode: "first person" }, HMD: { active: false },
        Messages: { messageReceived: signal(), subscribe() {}, unsubscribe() {} },
        AddressManager: { handleLookupString: (...args) => calls.push(["lookup", ...args]) },
        Window: { displayAnnouncement: text => calls.push(["announcement", text]) },
        UserActivityLogger: { palAction() {} }, print() {}
    });
    const tablet = Tablet.getTablet("com.highfidelity.interface.tablet.system");
    const open = () => tablet.buttons[0].click();
    open();
    return { Script, MyAvatar, AvatarBookmarks, Entities, calls, tablet, open,
        send: message => tablet.fromQml.emit(message) };
}

for (const [platform, touch] of [["Phone/iOS", true], ["Pico/Desktop", false]]) {
    test(platform + " Avatar linked pages use the existing browser and owner-selected injection", () => {
        for (const url of ["https://example.invalid/avatar-catalog", "http://example.invalid/public-catalog"]) {
            const h = start(touch);
            h.send({ method: "navigate", url });
            assert.equal(h.tablet.navigation.at(-1).type, "web");
            assert.deepEqual(h.tablet.navigation.at(-1).args,
                [url, "packaged:html/js/marketplacesInject.js"]);
            assert.equal(h.calls.length, 0);
            // Returning after failure/cancel restores the normal app receiver.
            h.open();
            h.send({ method: "navigate", url: "hifi://reference-world" });
            assert.deepEqual(h.calls.at(-1), ["lookup", "hifi://reference-world", false]);
            h.Script.end();
            assert.equal(h.tablet.fromQml.listenerCount, 0);
            assert.equal(h.tablet.buttons.length, 0);
        }
    });
}

test("Avatar browser handoff disconnects the app receiver until its own QML returns", () => {
    const h = start(true);
    h.send({ method: "navigate", url: "https://example.invalid/avatar-catalog" });
    const navigations = h.tablet.navigation.length;
    h.send({ method: "navigate", url: "https://example.invalid/stale-page" });
    assert.equal(h.tablet.navigation.length, navigations);
    assert.equal(h.tablet.fromQml.listenerCount, 0);
    h.open();
    assert.equal(h.tablet.fromQml.listenerCount, 1);
    h.Script.end();
});

test("Avatar navigation never accepts a page-selected injection or privileged component route", () => {
    const h = start(true);
    const navigations = h.tablet.navigation.length;
    for (const url of [null, {}, "file:///private/avatar.qml", "javascript:evil()", "qrc:/unapproved.qml"]) {
        h.send({ method: "navigate", url, scriptUrl: "https://example.invalid/evil.js" });
    }
    assert.equal(h.tablet.navigation.length, navigations);
    h.send({ method: "navigate", url: "https://example.invalid/avatar", scriptUrl: "https://example.invalid/evil.js" });
    assert.equal(h.tablet.navigation.at(-1).args[1], "packaged:html/js/marketplacesInject.js");
    h.Script.end();
});

test("Avatar URL, bookmarks, scale and wearables retain their ordinary operations", () => {
    const h = start(true);
    h.send({ method: "getAvatars" });
    h.send({ method: "applyExternalAvatar", avatarURL: "https://example.invalid/new.fst" });
    h.send({ method: "selectAvatar", name: "saved" });
    h.send({ method: "setScale", avatarScale: 1.25 });
    h.send({ method: "addAvatar", name: "new bookmark" });
    h.send({ method: "deleteAvatar", name: "new bookmark" });
    h.send({ method: "addWearable", url: "https://example.invalid/hat.fbx" });
    h.send({ method: "deleteWearable", entityID: "wearable-id" });
    assert.deepEqual(h.calls.slice(0, 5), [["avatar", "https://example.invalid/new.fst"],
        ["bookmark", "saved"], ["scale", 1.25], ["addBookmark", "new bookmark"], ["removeBookmark", "new bookmark"]]);
    assert.equal(h.calls[5][0], "wearable");
    assert.equal(h.calls[5][1].parentID, "self");
    assert.equal(h.calls[5][2], true);
    assert.deepEqual(h.calls[6], ["delete", "wearable-id"]);
    h.Script.end();
    assert.equal(h.Script.timers.size, 0);
    assert.equal(h.MyAvatar.targetScaleChanged.listenerCount, 0);
});
