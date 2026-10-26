// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Production Chat script; declared tablet/QML/message/Settings/native clocks.
// No real product, mixer, device or remote delivery is executed.
const path = require('node:path');
const readline = require('node:readline');
const root = process.argv[2];
const { FakeSignal, createScriptApi, createTabletApi, createMessagesApi, runProductionScript } =
    require(path.join(root, 'tests/javascript/support'));
const Script = createScriptApi(), Tablet = createTabletApi(), Messages = createMessagesApi();
const tablet = Tablet.getTablet('com.highfidelity.interface.tablet.system');
tablet.toolbarMode = true; tablet.tabletShown = true;
const values = new Map(), models = { local: [], domain: [] };
let epoch = 100000, offset = 0, sent = 0, echo = true;
class NativeClockDate extends Date {
    constructor(...args) { super(...(args.length ? args : [epoch])); }
    static now() { return epoch; }
}
Messages.sendMessage = (channel, message, localOnly = false) => {
    // Declared MessagesClient local self-echo seam, never a peer receipt.
    if (channel === 'chat') { ++sent; }
    if (Messages.subscriptions.has(channel) && (channel !== 'chat' || echo)) {
        Messages.messageReceived.emit(channel, message, 'controlled-self', localOnly);
    }
};
Messages.sendLocalMessage = (channel, message) => Messages.sendMessage(channel, message, true);
runProductionScript(path.join(root, 'scripts/communityScripts/armored-chat/armored_chat.js'), {
    Script, Tablet, Messages, Date: NativeClockDate,
    PlatformInfo: { getComputer: () => JSON.stringify({ OS: 'IOS' }) }, HMD: { active: false },
    Settings: { getValue: (key, fallback) => values.has(key) ? values.get(key) : fallback,
        setValue: (key, value) => values.set(key, value) },
    Controller: { keyPressEvent: new FakeSignal() },
    MyAvatar: { position: { x: 0, y: 0, z: 0 }, sessionDisplayName: 'Controlled' },
    AvatarManager: { getPalData: () => ({ data: [] }), avatarAddedEvent: new FakeSignal() },
    Users: { avatarDisconnected: new FakeSignal() },
    Vec3: { distance: (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) },
    console: { log: () => {} }
});
function output() {
    // Model only QML's original clear/show-message projection; retain the
    // actual producer stream separately from the actual saved Settings value.
    for (const row of tablet.qmlMessages.slice(offset)) {
        if (row.type === 'clear_messages') { models.local = []; models.domain = []; }
        if (row.type === 'show_message') { models[row.channel].push(row.message); }
    }
    offset = tablet.qmlMessages.length;
    const present = values.has('ArmoredChat-Messages'), stored = values.get('ArmoredChat-Messages');
    return { local: models.local, domain: models.domain, historyPresent: present,
        history: present ? stored : null, sent, subscriptions: Messages.subscriptions.size,
        qmlEvents: tablet.qmlMessages };
}
const input = readline.createInterface({ input: process.stdin });
input.on('line', line => {
    try {
        const command = JSON.parse(line);
        if (!Number.isSafeInteger(command.epoch) || command.epoch < epoch) { throw Error('Clock'); }
        epoch = command.epoch;
        if (command.action === 'open') { tablet.buttons[0].click(); tablet.fromQml.emit({ type: 'initialized' }); }
        else if (command.action === 'close') { tablet.fromQml.emit({ type: 'chat.close' }); }
        else if (command.action === 'send') {
            tablet.fromQml.emit({ type: 'send_message', message: command.text, channel: command.channel });
        } else if (command.action === 'typing') {
            tablet.fromQml.emit({ type: 'action', action: command.nonempty ? 'start_typing' : 'end_typing' });
        } else if (command.action === 'echo' && typeof command.enabled === 'boolean') {
            echo = command.enabled;
        } else if (command.action === 'end') { Script.end(); }
        else if (command.action !== 'read') { throw Error('Action'); }
        process.stdout.write(JSON.stringify({ ok: true, source: output() }) + '\n');
        if (command.action === 'end') { input.close(); }
    } catch (_error) {
        process.stdout.write(JSON.stringify({ ok: false }) + '\n'); process.exitCode = 1; input.close();
    }
});
