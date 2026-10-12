/**
 * Parent consent: a child without an e-mail registers with login + password,
 * waits on /konto/oczekuje, the parent opens the link from the e-mail (read
 * from GET /api/dev/outbox - the console e-mail backend) and decides.
 *
 * Each test registers a fresh, unique login, so reruns against the same stack
 * do not collide (RATE_LIMIT_NEW_USERS_PER_DAY in docker-compose.e2e.yml
 * leaves room for that).
 */

import { test, expect, Page, APIRequestContext } from '@playwright/test';

const PASSWORD = 'zielony rower w lesie';

function uniqueLogin(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`;
}

interface OutboxMessage {
  to: string;
  subject: string;
  links: string[];
}

/** Path + query of the first link to `path` in the newest e-mail to `to`. */
async function linkFromOutbox(request: APIRequestContext, to: string, path: string): Promise<string> {
  let found: string | undefined;
  await expect
    .poll(async () => {
      const response = await request.get('/api/dev/outbox');
      expect(response.ok()).toBe(true);
      const { messages } = (await response.json()) as { messages: OutboxMessage[] };
      // Newest message first; inside it the first link to `path` (the consent
      // e-mail also links "Nie zgadzam się" with &decyzja=nie, after "Wyrażam zgodę")
      const mail = messages.filter((m) => m.to === to).pop();
      const url = mail?.links.map((link) => new URL(link)).find((u) => u.pathname === path);
      found = url ? url.pathname + url.search : undefined;
      return found;
    })
    .toBeTruthy();
  return found!;
}

/** Walk the registration stepper as a child without an e-mail. */
async function registerWithLogin(page: Page, login: string, parentEmail: string): Promise<void> {
  await page.goto('/login');
  await page.getByRole('link', { name: /Załóż je/ }).click();
  await expect(page).toHaveURL(/\/rejestracja/);

  await page.getByLabel('Rok urodzenia').selectOption('2013');
  await page.getByRole('button', { name: 'Dalej' }).click();

  await page.getByRole('button', { name: /Nie mam adresu e-mail/ }).click();

  await page.getByLabel('Login').fill(login);
  await page.getByLabel('Hasło', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: 'Dalej' }).click();

  await page.getByLabel('E-mail rodzica lub opiekuna').fill(parentEmail);
  await page.getByRole('button', { name: 'Załóż konto' }).click();

  await expect(page).toHaveURL(/\/konto\/oczekuje/);
  await expect(page.getByRole('heading', { name: /Czekamy na zgodę rodzica/ })).toBeVisible();
}

test.describe('Parent consent for a login account', () => {
  test('parent confirms, the waiting screen flips and the app opens', async ({ page, browser }) => {
    const login = uniqueLogin('zgoda');
    const parentEmail = `rodzic.${login}@example.com`;

    await registerWithLogin(page, login, parentEmail);
    // The parent's address is shown masked
    await expect(page.getByText(/r\*\*\*@example\.com/)).toBeVisible();

    // While pending, writes are refused with a code the UI understands
    const blocked = await page.request.post('/api/patterns', { data: {} });
    expect(blocked.status()).toBe(403);
    expect((await blocked.json()).code).toBe('parent_consent_pending');

    // The parent, on another device
    const consentLink = await linkFromOutbox(page.request, parentEmail, '/rodzic/zgoda');
    const parentContext = await browser.newContext();
    const parentPage = await parentContext.newPage();
    await parentPage.goto(consentLink);
    await expect(parentPage.locator('#tresc-glowna').getByText(login, { exact: true })).toBeVisible();
    await parentPage.getByRole('button', { name: 'Wyrażam zgodę' }).click();
    await expect(parentPage.getByRole('heading', { name: 'Dziękujemy! Konto jest aktywne.' })).toBeVisible();
    // The parent is not logged in as the child
    const parentMe = await (await parentPage.request.get('/api/auth/me')).json();
    expect(parentMe.is_authenticated).toBe(false);
    await parentContext.close();

    // The child's waiting screen polls /api/auth/me every 10 s
    await expect(page.getByRole('heading', { name: 'Rodzic potwierdził konto!' })).toBeVisible({ timeout: 20000 });
    await page.getByRole('link', { name: 'Przejdź do zadań' }).click();
    await expect(page).toHaveURL(/\/years/);
    await expect(page.getByText(/czeka na zgodę rodzica/)).toHaveCount(0);

    const me = await (await page.request.get('/api/auth/me')).json();
    expect(me.account.status).toBe('active');
    expect(me.user.login).toBe(login);
  });

  test('parent declines and the account is gone', async ({ page, browser }) => {
    const login = uniqueLogin('odmowa');
    const parentEmail = `rodzic.${login}@example.com`;

    await registerWithLogin(page, login, parentEmail);

    const consentLink = await linkFromOutbox(page.request, parentEmail, '/rodzic/zgoda');
    const parentContext = await browser.newContext();
    const parentPage = await parentContext.newPage();
    // The "Nie zgadzam się" button in the e-mail adds decyzja=nie: the page opens
    // the confirmation straight away, but nothing happens until the parent confirms
    await parentPage.goto(`${consentLink}&decyzja=nie`);
    const dialog = parentPage.getByRole('dialog', { name: 'Usunąć konto dziecka?' });
    await expect(dialog).toBeVisible();
    const before = await (await page.request.get('/api/auth/me')).json();
    expect(before.account.status).toBe('pending_parent');
    await dialog.getByRole('button', { name: 'Tak, usuń konto' }).click();
    await expect(parentPage.getByRole('heading', { name: 'Konto zostało usunięte' })).toBeVisible();

    // The link cannot be used again
    await parentPage.reload();
    await expect(parentPage.getByRole('button', { name: 'Wyrażam zgodę' })).toHaveCount(0);
    await parentContext.close();

    // The child's session ended with the account
    await expect
      .poll(async () => (await (await page.request.get('/api/auth/me')).json()).is_authenticated)
      .toBe(false);

    // And the login no longer works
    const response = await page.request.post('/api/auth/login', {
      data: { login, password: PASSWORD, remember: false },
    });
    expect(response.status()).toBe(401);
  });
});
