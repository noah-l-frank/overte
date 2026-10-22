// SPDX-License-Identifier: Apache-2.0
// Real production-browser acceptance for local UI/rendering. Native session,
// voice interoperability and hardware journeys retain their separate owners.
import {test, expect} from '@playwright/test';

test('production renderer and disconnected tablet journey', async ({page}) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('/');
    await page.waitForFunction(() => typeof (window as any).overteDirectDiagnostics === 'function');
    const renderer = await page.evaluate(() => {
        const canvas = document.querySelector<HTMLCanvasElement>('#world canvas');
        const gl = canvas?.getContext('webgl2');
        const debug = gl?.getExtension('WEBGL_debug_renderer_info');
        return {secure: isSecureContext, width: canvas?.width, height: canvas?.height,
            webgl2: Boolean(gl), renderer: debug ? gl?.getParameter(debug.UNMASKED_RENDERER_WEBGL)
                : gl?.getParameter(gl.RENDERER),
            media: document.querySelectorAll('video,audio,iframe').length};
    });
    expect(renderer.secure).toBe(true);
    expect(renderer.webgl2).toBe(true);
    expect(renderer.width).toBeGreaterThan(0);
    expect(renderer.height).toBeGreaterThan(0);
    expect(renderer.renderer).toMatch(/swiftshader|llvmpipe|swrast|software/i);
    expect(renderer.media).toBe(0);

    for (const app of ['Domain', 'People', 'Avatar', 'Audio', 'Graphics', 'Snapshot']) {
        await page.locator(`button[aria-controls="tablet-${app.toLowerCase()}"]`).click();
        await expect.poll(() => page.evaluate(() => (window as any).overteDirectDiagnostics().tablet.app)).toBe(app);
    }
    await page.locator('button[aria-controls="tablet-audio"]').click();
    await expect(page.locator('#tablet-audio button').first()).toBeDisabled();
    await page.locator('button[aria-controls="tablet-graphics"]').click();
    const slider = page.locator('#tablet-graphics label:first-of-type input[type="range"]');
    const initial = await slider.inputValue();
    await slider.focus();
    await page.keyboard.press('ArrowLeft');
    await expect(page.locator('#notice')).toContainText('Graphics setting applied');
    await expect(slider).not.toHaveValue(initial);
    await page.keyboard.press('ArrowRight');
    await expect(slider).toHaveValue(initial);
    await page.locator('button[aria-controls="tablet-domain"]').click();
    expect(errors).toEqual([]);
});
