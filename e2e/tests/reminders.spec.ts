/**
 * Phone reminders about due wzorce ("Przypomnienia na telefonie").
 *
 * The E2E API has a throwaway VAPID key pair (docker-compose.e2e.yml). The
 * browser's push service is stubbed: PushManager returns a fake FCM
 * subscription. The API's delivery loop is off in E2E_MODE and no spec sends
 * a test notification, so nothing is posted to a real push service. Real delivery is covered
 * by app/push unit tests (fake sender) and a manual check on a phone.
 */

import { test, expect } from '@playwright/test';
import { loginAs, TEST_USERS } from './utils/auth';

const FAKE_ENDPOINT = 'https://fcm.googleapis.com/fcm/send/e2e-device';

test.describe('Przypomnienia na telefonie', () => {
  test.beforeEach(async ({ context }) => {
    await loginAs(context, TEST_USERS.default);
  });

  test('installable app: manifest and service worker', async ({ page }) => {
    const manifest = await (await page.request.get('/manifest.webmanifest')).json();
    expect(manifest.display).toBe('standalone');
    expect(manifest.start_url).toBe('/wzorce');
    expect(manifest.icons.some((i: { sizes: string }) => i.sizes === '512x512')).toBeTruthy();

    const sw = await page.request.get('/sw.js');
    expect(sw.ok()).toBeTruthy();
    expect(sw.headers()['cache-control']).toContain('no-cache');
    expect(await sw.text()).toContain('notificationclick');
  });

  test('switch on, change the times, switch off', async ({ page }) => {
    await page.addInitScript((endpoint) => {
      Object.defineProperty(Notification, 'permission', { get: () => 'granted' });
      Notification.requestPermission = async () => 'granted';
      let current: object | null = null;
      const fake = () => ({
        endpoint,
        options: { applicationServerKey: null },
        toJSON: () => ({
          endpoint,
          keys: {
            p256dh: 'BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM',
            auth: 'tBHItJI5svbpez7KI4CCXg',
          },
        }),
        unsubscribe: async () => {
          current = null;
          return true;
        },
      });
      PushManager.prototype.subscribe = async function () {
        current = fake();
        return current as PushSubscription;
      };
      PushManager.prototype.getSubscription = async function () {
        return current as PushSubscription | null;
      };
    }, FAKE_ENDPOINT);

    await page.goto('/wzorce');
    const card = page.getByTestId('reminder-card');
    await card.getByTestId('reminder-enable').click();
    await expect(card.getByTestId('reminder-on')).toBeVisible();

    const config = await (await page.request.get('/api/push/config')).json();
    expect(config.devices).toBeGreaterThanOrEqual(1);

    await card.getByLabel('Dni szkolne (pn-pt)').fill('17:15');
    await card.getByRole('button', { name: 'Zapisz godziny' }).click();
    await expect(card.getByText('Zapisano godziny przypomnień.')).toBeVisible();
    expect((await (await page.request.get('/api/push/config')).json()).weekday_time).toBe('17:15');

    await card.getByRole('button', { name: 'Wyłącz na tym urządzeniu' }).click();
    await expect(card.getByTestId('reminder-enable')).toBeVisible();
    // Back to the defaults for the next run
    await page.request.put('/api/push/settings', { data: { weekday_time: '16:30', weekend_time: '10:00' } });
  });

  test('iPhone outside the installed app: install instructions', async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'userAgent', {
        get: () => 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
      });
      // Safari outside a Home Screen app exposes no Push API
      delete (window as unknown as Record<string, unknown>).PushManager;
    });
    await page.goto('/wzorce');
    await expect(page.getByTestId('reminder-ios-install')).toContainText('Do ekranu początkowego');
  });
});
