"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const crypto = require("node:crypto");
const path = require("node:path");
const test = require("node:test");
const { createScriptApi, createTabletApi, runProductionScript } = require("../support");

const source = path.resolve(__dirname,
    "../../../scripts/system/+android_phoneInterface/phoneEmote.js");
const agreedEmotes = ["Crying", "Surprised", "Dancing", "Cheering", "Waving",
    "Fall", "Pointing", "Clapping", "Sit", "Love"];
const assetRecords = new Map();
const observations = [];
const recordedClicks = process.env.OVERTE_EMOTE_QML_ACTIONS
    ? JSON.parse(fs.readFileSync(process.env.OVERTE_EMOTE_QML_ACTIONS, "utf8")) : null;
if (recordedClicks) {
    assert.deepEqual(recordedClicks, agreedEmotes.map((name) => ({ method: "phoneEmote.play", name })),
        "Actual QML mouse clicks must dispatch all ten agreed actions in order");
}

function checkBundledAsset(url) {
    if (!assetRecords.has(url)) {
        const bytes = fs.readFileSync(url);
        assert.equal(bytes.subarray(0, 23).toString("binary"), "Kaydara FBX Binary  \x00\x1a\x00");
        assert.ok(bytes.includes(Buffer.from("AnimationCurve")), `${url} contains no animation curves`);
        assetRecords.set(url, { path: url, bytes: bytes.length,
            sha256: crypto.createHash("sha256").update(bytes).digest("hex") });
    }
}

function start({ resourceState = 3, frames = 120, random = 0, frameData } = {}) {
    const Script = createScriptApi();
    Script.resolvePath = (value) => path.resolve(path.dirname(source), value);
    const Tablet = createTabletApi();
    const avatarCalls = [];
    const MyAvatar = {
        overrideAnimation(...args) { avatarCalls.push(["override", ...args]); },
        restoreAnimation() { avatarCalls.push(["restore"]); }
    };
    // Native decoding/cache and avatar animation are explicit seams. Resolve
    // actual production URLs to the real bundled FBX bytes; do not claim decode.
    const resources = new Map();
    const animationRequests = [];
    const AnimationCache = {
        prefetch(url) { checkBundledAsset(url); const resource = { state: resourceState }; resources.set(url, resource); return resource; },
        getAnimation(url) { checkBundledAsset(url); animationRequests.push(url); return { frames: frameData === undefined ? { length: frames } : frameData }; }
    };
    const math = Object.create(Math);
    math.random = () => random;
    runProductionScript(source, { AnimationCache, MyAvatar, Script, Tablet, Math: math });
    return {
        AnimationCache, MyAvatar, Script, avatarCalls, resources, animationRequests,
        tablet: Tablet.getTablet("com.highfidelity.interface.tablet.system")
    };
}

function openApp(tablet) {
    const button = tablet.buttons[0];
    button.click();
    const appSource = tablet.navigation.at(-1).args[0];
    assert.equal(appSource, path.resolve(path.dirname(source), "PhoneEmote.qml"));
    return button;
}

test("production emote app plays an allowlisted animation and completes it", () => {
    const { Script, avatarCalls, tablet } = start();
    openApp(tablet);
    tablet.fromQml.emit({ method: "phoneEmote.ready" });
    tablet.fromQml.emit({ method: "phoneEmote.play", name: "Waving" });

    assert.equal(avatarCalls[0][0], "override");
    assert.match(avatarCalls[0][1], /Waving[.]fbx$/);
    assert.equal(tablet.qmlMessages.at(-1).active, "Waving");
    const timer = [...Script.timers.keys()][0];
    assert.equal(Script.timers.get(timer).delay, 2000);

    Script.runTimer(timer);
    assert.equal(avatarCalls.at(-1)[0], "restore");
    assert.equal(tablet.qmlMessages.at(-1).active, "");
    assert.equal(tablet.qmlMessages.at(-1).status, "Choose an emote");
});

for (const [index, name] of agreedEmotes.entries()) {
    test(`actual production event dispatch plays and completes bundled ${name}`, () => {
        const state = start();
        openApp(state.tablet);
        state.tablet.fromQml.emit(recordedClicks ? recordedClicks[index] : { method: "phoneEmote.play", name });
        assert.deepEqual(state.avatarCalls[0], ["override",
            path.resolve(path.dirname(source), `../assets/animations/${name === "Sit" ? "Sit1" : name}.fbx`),
            60, false, 0, 120]);
        assert.equal(state.tablet.qmlMessages.at(-1).active, name);
        assert.equal(state.tablet.qmlMessages.at(-1).status, `Playing ${name}`);
        assert.equal(state.Script.timers.size, 1);
        const [id, timer] = [...state.Script.timers][0];
        assert.equal(timer.delay, 2000);
        state.Script.runTimer(id);
        assert.deepEqual(state.avatarCalls.at(-1), ["restore"]);
        assert.equal(state.tablet.qmlMessages.at(-1).active, "");
        assert.equal(state.Script.timers.size, 0);
        observations.push({ action: name, dispatch: recordedClicks ? "actual Qt Quick mouse click" : "tablet.fromQml",
            animation: state.avatarCalls[0][1], completion: state.tablet.qmlMessages.at(-1).status });
    });
}

test("all twelve real bundled animation files are requested by production startup", () => {
    const state = start();
    const expected = [...agreedEmotes.filter((name) => name !== "Sit"), "Sit1", "Sit2", "Sit3"]
        .map((name) => path.resolve(path.dirname(source), `../assets/animations/${name}.fbx`)).sort();
    assert.deepEqual([...state.resources.keys()].sort(), expected);
    assert.deepEqual(state.animationRequests.sort(), expected);
});

for (const [random, file] of [[0, "Sit1"], [0.5, "Sit2"], [0.999, "Sit3"]]) {
    test(`actual random-selection boundary reaches bundled ${file}`, () => {
        const state = start({ random });
        openApp(state.tablet);
        state.tablet.fromQml.emit({ method: "phoneEmote.play", name: "Sit" });
        assert.equal(path.basename(state.avatarCalls[0][1]), `${file}.fbx`);
        assert.equal(state.tablet.qmlMessages.at(-1).active, "Sit");
        state.Script.end();
        assert.deepEqual(state.avatarCalls.at(-1), ["restore"]);
        assert.equal(state.Script.timers.size, 0);
        observations.push({ action: "Sit", randomInput: random, animation: file, teardown: "restored" });
    });
}

test("same-name toggle cancels its timer and another emote replaces the previous animation", () => {
    const state = start();
    openApp(state.tablet);
    const play = (name) => state.tablet.fromQml.emit({ method: "phoneEmote.play", name });
    play("Love");
    const first = [...state.Script.timers.keys()][0];
    play("Love");
    assert.deepEqual(state.avatarCalls.map((call) => call[0]), ["override", "restore"]);
    assert.equal(state.Script.runTimer(first), false);
    assert.equal(state.tablet.qmlMessages.at(-1).active, "");
    play("Waving");
    const replaced = [...state.Script.timers.keys()][0];
    play("Cheering");
    assert.deepEqual(state.avatarCalls.slice(-2).map((call) => call[0]), ["restore", "override"]);
    assert.equal(state.Script.runTimer(replaced), false);
    assert.equal(state.Script.timers.size, 1);
    state.Script.end();
    assert.equal(state.Script.timers.size, 0);
    assert.deepEqual(state.avatarCalls.at(-1), ["restore"]);
});

for (const resourceState of [0, 1, 2]) {
    test(`in-progress resource state ${resourceState} reports loading then plays after the cache reports ready`, () => {
        const state = start({ resourceState });
        openApp(state.tablet);
        state.tablet.fromQml.emit({ method: "phoneEmote.play", name: "Waving" });
        assert.equal(state.tablet.qmlMessages.at(-1).status, "Animation is still loading");
        assert.equal(state.avatarCalls.length, 0);
        assert.equal(state.Script.timers.size, 0);
        state.resources.get(path.resolve(path.dirname(source), "../assets/animations/Waving.fbx")).state = 3;
        state.tablet.fromQml.emit({ method: "phoneEmote.play", name: "Waving" });
        assert.equal(state.avatarCalls[0][0], "override");
        assert.equal(state.tablet.qmlMessages.at(-1).status, "Playing Waving");
    });
}

test("terminal native resource failure reports an error without fabricating playback or recovery", () => {
    const state = start({ resourceState: 4 });
    openApp(state.tablet);
    const event = recordedClicks ? recordedClicks[4] : { method: "phoneEmote.play", name: "Waving" };
    for (let attempt = 0; attempt < 2; ++attempt) {
        state.tablet.fromQml.emit(event);
        assert.equal(state.tablet.qmlMessages.at(-1).status, "Animation failed to load");
        assert.equal(state.avatarCalls.length, 0);
        assert.equal(state.Script.timers.size, 0);
    }
    state.resources.get(path.resolve(path.dirname(source), "../assets/animations/Waving.fbx")).state = 3;
    state.tablet.fromQml.emit(event);
    assert.equal(state.avatarCalls[0][0], "override");
});

test("a failed selection preserves the current working emote until its cache really becomes ready", () => {
    const state = start();
    openApp(state.tablet);
    state.tablet.fromQml.emit({ method: "phoneEmote.play", name: "Love" });
    const playingTimer = [...state.Script.timers.keys()][0];
    const waving = state.resources.get(path.resolve(path.dirname(source), "../assets/animations/Waving.fbx"));
    waving.state = 4;
    state.tablet.fromQml.emit({ method: "phoneEmote.play", name: "Waving" });
    assert.equal(state.tablet.qmlMessages.at(-1).status, "Animation failed to load");
    assert.equal(state.tablet.qmlMessages.at(-1).active, "Love");
    assert.equal(state.avatarCalls.length, 1);
    assert.equal(state.Script.timers.has(playingTimer), true);
    waving.state = 3;
    state.tablet.fromQml.emit({ method: "phoneEmote.play", name: "Waving" });
    assert.deepEqual(state.avatarCalls.slice(-2).map((call) => call[0]), ["restore", "override"]);
    assert.equal(state.Script.timers.has(playingTimer), false);
});

for (const [label, frameData] of [["absent", null], ["zero", { length: 0 }],
    ["negative", { length: -1 }], ["NaN", { length: NaN }], ["infinite", { length: Infinity }]]) {
    test(`invalid cached frames (${label}) never start an animation`, () => {
        const state = start({ frameData });
        openApp(state.tablet);
        state.tablet.fromQml.emit({ method: "phoneEmote.play", name: "Fall" });
        assert.equal(state.avatarCalls.length, 0);
        assert.equal(state.Script.timers.size, 0);
        assert.equal(state.tablet.qmlMessages.at(-1).active, "");
    });
}

test("inactive screens and malformed messages cannot start playback or retain signal owners", () => {
    const state = start();
    state.tablet.fromQml.emit({ method: "phoneEmote.play", name: "Clapping" });
    assert.equal(state.avatarCalls.length, 0);
    const button = openApp(state.tablet);
    for (const message of [null, false, "play", {}, { method: 1 }, { method: "phoneEmote.play", name: 1 }]) {
        state.tablet.fromQml.emit(message);
    }
    assert.equal(state.avatarCalls.length, 0);
    state.tablet.fromQml.emit({ method: "phoneEmote.play", name: "Clapping" });
    button.click();
    assert.equal(state.tablet.navigation.at(-1).type, "home");
    assert.equal(state.Script.timers.size, 0);
    assert.deepEqual(state.avatarCalls.at(-1), ["restore"]);
    state.Script.end();
    assert.equal(state.tablet.screenChanged.listenerCount, 0);
    assert.equal(state.tablet.fromQml.listenerCount, 0);
    assert.equal(button.clicked.listenerCount, 0);
});

test.after(() => {
    if (process.env.OVERTE_EMOTE_JS_EVIDENCE) {
        fs.writeFileSync(process.env.OVERTE_EMOTE_JS_EVIDENCE, JSON.stringify({ source,
            sourceSha256: crypto.createHash("sha256").update(fs.readFileSync(source)).digest("hex"),
            boundary: "Actual production JS and bundled FBX bytes; native cache decoding, avatar effects and timers are explicit seams",
            actualQmlClicks: recordedClicks, observations, assets: [...assetRecords.values()] }, null, 2) + "\n");
    }
});

test("production emote app rejects unknown and unavailable animations", () => {
    const unavailable = start({ resourceState: 1 });
    openApp(unavailable.tablet);
    unavailable.tablet.fromQml.emit({ method: "phoneEmote.play", name: "Waving" });
    assert.equal(unavailable.tablet.qmlMessages.at(-1).status, "Animation is still loading");
    assert.equal(unavailable.avatarCalls.length, 0);

    unavailable.tablet.fromQml.emit({ method: "phoneEmote.play", name: "../../evil" });
    assert.equal(unavailable.tablet.qmlMessages.at(-1).status, "Unsupported emote");
    assert.equal(unavailable.Script.timers.size, 0);
});

test("production emote app stops playback when closed and cleans up on shutdown", () => {
    const { Script, avatarCalls, tablet } = start();
    const button = openApp(tablet);
    tablet.fromQml.emit({ method: "phoneEmote.play", name: "Crying" });
    tablet.screenChanged.emit("Home", "");

    assert.equal(avatarCalls.at(-1)[0], "restore");
    assert.equal(Script.timers.size, 0);
    Script.end();
    assert.equal(tablet.buttons.length, 0);
    assert.equal(button.clicked.listenerCount, 0);
    assert.equal(tablet.fromQml.listenerCount, 0);
});
