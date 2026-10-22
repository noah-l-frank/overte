// SPDX-License-Identifier: Apache-2.0
import { defineConfig, devices } from '@playwright/test';
import { lstatSync, accessSync, constants } from 'node:fs';
import { isAbsolute } from 'node:path';

// The controller prepares this executable outside the untrusted checkout and
// mounts it read-only. Never download a browser from a candidate test command.
const executablePath = process.env.OVERTE_BROWSER_CHROME_EXECUTABLE;
if (executablePath !== undefined) {
    if (!isAbsolute(executablePath) || !lstatSync(executablePath).isFile()
            || lstatSync(executablePath).isSymbolicLink()) throw Error('Invalid prepared Chrome executable');
    accessSync(executablePath, constants.X_OK);
}

export default defineConfig({
    testDir: './e2e', testMatch: 'standalone.browser.spec.ts',
    timeout: 45_000, expect: {timeout: 10_000}, workers: 1,
    reporter: [['list']],
    use: {baseURL: 'http://127.0.0.1:5173', screenshot: 'only-on-failure'},
    projects: [{name: 'standalone-chrome', use: {
        ...devices['Desktop Chrome'], ...(executablePath ? {} : {channel: 'chrome'}),
        launchOptions: {executablePath, args: ['--use-angle=swiftshader',
            ...(process.env.OVERTE_BROWSER_CI_ISOLATED === '1' ? ['--no-sandbox'] : [])]},
    }}],
    webServer: {command: 'npm run preview -- --port 5173 --strictPort',
        url: 'http://127.0.0.1:5173', reuseExistingServer: false},
});
