# Under-16 accounts with parent consent, login/password accounts, transactional e-mail — design

Date: 2026-10-12
Status: approved by the owner in chat 2026-10-12, to be implemented on `feat/under-16-parent-consent`

## Context and goal

The public service (`omj-validator.pl`, variant A in `docs/rodo/README.md`) processes
personal data on consent (art. 6(1)(a) RODO). In Poland a child can consent alone
only from 16 (art. 8 RODO + art. 8 of the 2018 Polish act). OMJ's audience is
12–15. Today the only safeguard is the checkbox in `LoginForm.tsx`: "I accept the
terms and agree to processing" — a child's declaration, not a parent's consent.
Art. 8(2) asks for "reasonable efforts" to verify parental consent; for a low-risk
service the EDPB (Guidelines 05/2020 on consent, §§ 132–137) accepts verification
by e-mail. A teacher at school 221 also asked how pupils without any e-mail
(no school Google Workspace for pupils) could use the app.

This feature adds:

1. an age step on registration (year of birth),
2. parent consent by e-mail for everyone under 16 — the account exists but is
   inert until a parent confirms it,
3. login + password accounts for children without an e-mail; these always have a
   parent e-mail, and password reset goes to the parent,
4. a parent page reachable from every e-mail: see the children's accounts, delete
   an account, set a new password,
5. the same age/consent step for existing accounts on their next visit,
6. transactional e-mail through Resend (domain already verified, EU region),
7. `/regulamin`, `docs/rodo/dpia.md` and `docs/rodo/README.md` updated.

Out of scope (owner decision 2026-10-12): teacher accounts, classes, a parent
account with a password, a parent preview of submissions, linking a login
account to Google later.

### Decisions made

| Question | Decision |
|---|---|
| Age question | Year of birth (select), not a "16+" checkbox. If `current_year - birth_year == 16` ask a follow-up "Czy masz już ukończone 16 lat?" |
| Who needs a parent | Everyone under 16 (any login method) and **every login/password account** regardless of age (the parent e-mail is the only recovery contact) |
| Google login | Stays. Unknown Google identity → no user row yet; finish registration (age, parent e-mail) first |
| Login accounts | `login` + password + birth year + parent e-mail. No child e-mail collected |
| Pending account | Logged in, can read public pages, cannot submit or call AI or save anything. Deleted with all data 14 days after `pending_since` if no consent |
| Parent decline | "Nie zgadzam się" deletes the account at once |
| Withdrawal | Parent page "Usuń konto dziecka" = withdrawal; deletes everything (no separate "withdrawn" state) |
| Existing accounts | On next visit: year of birth; under 16 → parent e-mail → pending (14-day rule applies, warned on screen). Owner decision 2026-10-12 |
| E-mail provider | Resend, `omj-validator.pl` verified, sending region eu-west-1, Resend is EU–US DPF certified, DPA at resend.com/legal/dpa |
| Sender | `From: OMJ Validator <noreply@omj-validator.pl>`, `Reply-To: kontakt@omj-validator.pl` (Cloudflare routes it to the owner's inbox) |
| Teacher features | None in this feature |

## Data model

### `users` — the primary key stops being Google's

`users.google_sub` is the primary key and every `user_id` foreign key points at
it. Rename the column to `id` (same type, `String(255)`), keep every existing
value (for existing users `id == their Google sub`, so no foreign-key value
changes and no upload directory moves). Then:

| Column | Change |
|---|---|
| `id` | renamed from `google_sub`; new users get `uuid4().hex` |
| `google_sub` | new, nullable, unique; backfilled `= id` for existing rows |
| `email` | becomes nullable (login accounts have none); stays unique |
| `login` | new, nullable, unique, stored lower-case, `^[a-z0-9][a-z0-9._-]{2,31}$` |
| `password_hash` | new, nullable, argon2id (`argon2-cffi`) |
| `birth_year` | new, nullable `SmallInteger`; `NULL` = not asked yet (existing users) |
| `status` | new, `active` / `pending_parent`; existing rows `active` |
| `pending_since` | new, nullable timestamp; set when entering `pending_parent` |
| `parent_id` | new, nullable FK → `parents.id` |
| `session_version` | new, int default 0; bumped on password reset; sessions carrying an older value are rejected |

Check constraint: `google_sub IS NOT NULL OR (login IS NOT NULL AND password_hash IS NOT NULL)`.
Check constraint: `login IS NULL OR parent_id IS NOT NULL`.

Every Python, TypeScript and test reference to `google_sub` as "the user id"
becomes `id` (repositories, `main.py`, `retention.py`, admin components,
`lib/types`, e2e `seed_test_users.py` / `utils/auth.ts`). `google_sub` remains
only where the Google identity is meant (OAuth callback, lookup).

**Sessions:** the session dict gains `user_id` and `session_version`. A session
that still carries only `google_sub` (logged in before deploy) is accepted by
reading `google_sub` as `user_id` (values are equal for existing users), then
rewritten — nobody is logged out by the deploy.

### `parents`

| Column | |
|---|---|
| `id` | `uuid4().hex` PK |
| `email` | unique, lower-cased, trimmed |
| `created_at` | |

A parent row is deleted when its last child is deleted (same transaction).
Several children may share one parent e-mail (siblings).

### `consents`

| Column | |
|---|---|
| `id` | int PK |
| `user_id` | FK users CASCADE |
| `kind` | `self` (16+, ticked the checkbox) / `parent` (parent clicked the confirm button) |
| `parent_id` | nullable FK parents |
| `terms_version` | string, `TERMS_VERSION` setting (date of the `/regulamin` text, e.g. `2026-10-12`) |
| `given_at` | timestamp |

No IP, no user agent (minimisation). This is the art. 7(1) proof. Deleted with the account.

### `email_tokens`

| Column | |
|---|---|
| `id` | int PK |
| `token_hash` | SHA-256 hex of the random token (`secrets.token_urlsafe(32)`); the raw token exists only in the e-mail |
| `purpose` | `consent` / `password_reset` / `parent_manage` |
| `user_id` | nullable FK users CASCADE (consent, reset) |
| `parent_id` | FK parents CASCADE |
| `created_at`, `expires_at`, `used_at` | consent 14 days, reset 1 hour, manage 30 days; consent and reset are single-use, manage is reusable until expiry |

Rows double as the send log for rate limits (count by `parent_id` / `user_id`
in the last 24 h). Purged by the retention pass 30 days after `expires_at`.

### `login_failures`

`(id, login, ip_hash, at)` — `ip_hash` = HMAC of the IP with the session secret.
Purged after 24 h by the retention pass.

## Flows

### Registration — `/rejestracja` (new page; `/login` links to it: "Nie masz konta? Załóż je")

Stepper, one question per screen, MUI like the rest of the app, works at 360 px:

1. **Rok urodzenia** — select. If the year makes the age ambiguous (16 this
   year) ask "Czy masz już ukończone 16 lat?" (Tak / Nie). Years outside
   `current_year-100 … current_year-6` are not offered.
2. **Jak chcesz się logować?**
   - "Mam konto Google" → Google button.
   - "Nie mam adresu e-mail — utworzę login i hasło" → login + password form.
3. **Under 16 or login account:** "Adres e-mail rodzica lub opiekuna" + one line
   why ("Wyślemy rodzicowi prośbę o zgodę. Bez niej nie będziesz mógł/mogła
   przesyłać rozwiązań."). Must differ from the child's Google e-mail.
   **16+ with Google:** the existing terms checkbox (`kind = self` consent).
4. Submit → account created → logged in.
   - `active` (16+ Google) → `/years` as today.
   - `pending_parent` → `/konto/oczekuje`.

Google ordering: the age / parent answers are stored in the session before
the Google redirect (`pending_registration`). In the callback:
- known `google_sub` → normal login (existing behaviour, plus the legacy check below);
- unknown + `pending_registration` in session → create the user from it;
- unknown, no `pending_registration` (child clicked "Zaloguj przez Google" on `/login`
  without an account) → store `{sub, email, name}` as `pending_google` in the
  session, **create nothing**, redirect to `/rejestracja?google=1`, which skips
  step 2. `pending_google` lives 30 minutes.

The new-user daily limit (`rate_limit_new_users_per_day`) applies to both paths.

Login form validation (shown inline, Polish):
- login: 3–32 chars, letters, digits, `.`, `_`, `-`; hint "Nie używaj imienia i nazwiska.";
  "Ten login jest zajęty" checked on blur (rate-limited endpoint).
- password: min 8 characters, not in a bundled list of the 10 000 most common
  passwords, not equal to the login; hint "Najłatwiej zapamiętać kilka słów, np. «zielony rower w lesie»"; a show/hide toggle; no composition rules, no second "repeat password" field (show/hide replaces it).

### Pending screen — `/konto/oczekuje`

- Heading "Prawie gotowe! Czekamy na zgodę rodzica"
- "Wysłaliśmy wiadomość na adres a***@gmail.com. Poproś rodzica, żeby ją otworzył
  i kliknął «Wyrażam zgodę». Sprawdźcie też folder Spam / Oferty."
- "Wyślij ponownie" (disabled for 60 s after each send; max 3 consent e-mails per
  account per 24 h and 5 per parent address per 24 h — beyond that a calm message
  "Wysłaliśmy już kilka wiadomości. Spróbuj jutro.")
- "Zmień adres e-mail rodzica" (inline form; counts against the same limits; old
  consent tokens invalidated)
- "Jeśli rodzic nie potwierdzi konta w ciągu 14 dni, usuniemy je razem ze wszystkimi danymi." (show the date)
- "Wyloguj"
- The page polls `/api/auth/me` every 10 s (and on focus); when the status turns
  `active` it shows a short success state ("Rodzic potwierdził konto!") with a
  button to `/years`.

While pending, everywhere else: a slim banner under the header linking to
`/konto/oczekuje`; every write / AI endpoint (submit, private tasks, patterns,
account changes other than delete and parent e-mail change) answers
`403 {"detail": ..., "code": "parent_consent_pending"}`. Implement as one
dependency (`require_active_user`) applied at the router level where possible so
a future endpoint does not forget it. Self-service account deletion stays allowed.

### Existing accounts (birth_year IS NULL)

`/api/auth/me` returns `needs_profile: true`. The frontend sends such a user to
`/konto/uzupelnij` from any page except `/regulamin` and `/logout`:
"Uzupełnij jedną informację" → year of birth (+ the 16 follow-up). 16+ →
`self` consent recorded, done. Under 16 → parent e-mail → `pending_parent`
(existing data kept; the 14-day rule and its warning apply). Write endpoints
answer `403 code=profile_incomplete` until done.

### Parent e-mail: consent request

Subject: `Prośba o zgodę — konto Twojego dziecka w OMJ Validator`

Content (Polish, short, warm, no marketing):
- who we are, one sentence: free, non-commercial trainer for the Olimpiada
  Matematyczna Juniorów, run by a private person (name from `/regulamin`);
- which account: Google e-mail of the child, or `login: <login>` for login
  accounts. **No other child-provided text** (no Google display name);
- what we process: photos / typed solutions, assessed automatically by an AI
  model (same wording as `/regulamin`), how long we keep them (from the
  retention constants), the parent can delete the account at any time;
- two buttons: **"Wyrażam zgodę"** and **"Nie zgadzam się — usuń konto"**, and a
  link to `/regulamin`;
- footer: why you got this e-mail ("Ktoś podał ten adres jako adres rodzica przy
  zakładaniu konta. Jeśli to pomyłka, po prostu zignoruj tę wiadomość — konto
  zostanie usunięte po 14 dniach."), `kontakt@omj-validator.pl`.

**Buttons open a page, they never act on GET** (mail scanners and link
previewers open links): `/rodzic/zgoda?t=<token>` shows the account and the
summary with two buttons that POST. Expired / used token → friendly page with
"Wyślij nowy link" (only when the account is still pending: sends a new consent
e-mail, same limits).

After confirming: `status=active`, `pending_since=NULL`, `parent` consent row,
the token used, a second e-mail **"Konto Twojego dziecka jest aktywne"** with
the manage link, and the page shows "Dziękujemy! Konto jest aktywne." plus the
manage link.

After declining: account deleted with the existing erasure routine
(`app/retention.py`), page "Konto zostało usunięte. Nie zapisaliśmy żadnych danych dziecka."

### Parent page — `/rodzic`

- `/rodzic?t=<manage token>` — lists all children with this parent e-mail:
  identifier (Google e-mail or login), created date, status. Actions per child:
  - "Usuń konto i wszystkie dane" (confirm dialog) → erasure;
  - login accounts: "Ustaw nowe hasło" (same password rules) → bumps `session_version`.
- `/rodzic` without a token: "Wpisz swój adres e-mail, wyślemy Ci link" → always
  answers "Jeśli ten adres jest powiązany z kontem dziecka, wysłaliśmy link." (max 3 per address per 24 h).
- Every e-mail to a parent carries a manage link.

### Password reset — login accounts

`/login` (login form) → "Nie pamiętam hasła" → `/reset-hasla`: enter login →
always "Jeśli takie konto istnieje, wysłaliśmy rodzicowi link do zmiany hasła."
E-mail to the parent: "Zmiana hasła — konto <login>", button to
`/reset-hasla/nowe?t=<token>` (page, POST on submit), valid 1 h, single use;
setting the password bumps `session_version`; a reset link never logs anyone in
(the parent is likely on their own phone) — it shows "Hasło zmienione. Możesz się
zalogować."
Limits: 3 reset e-mails per account per 24 h.

### Login page — `/login`

Two clear options: Google button (as today) and a login form (login, password,
"Zapamiętaj mnie na tym urządzeniu" unchecked by default, "Nie pamiętam
hasła"). The terms checkbox moves to registration (`self` consent) — logging
into an existing account no longer needs it. Without "Zapamiętaj mnie" the
session ends 12 h after login (stored expiry in the session dict, checked in
`get_current_user`); with it, the existing 30 days.

Brute force: 5 failed logins per login per 15 min → that login refuses for 15
min; 20 per IP per 15 min. One generic error "Nieprawidłowy login lub hasło"
for unknown login and wrong password; the lockout message is the same for
existing and non-existing logins.

## E-mail sending

`app/email/` (or `app/mailer.py`, the implementer's call):
- `send_email(to, subject, html, text)`; `EMAIL_BACKEND=console|resend`.
  - `resend`: `POST https://api.resend.com/emails` with `httpx`, `RESEND_API_KEY`,
    timeout 10 s. Failure → logged (masked address, no body) and surfaced to the
    caller, which shows "Nie udało się wysłać wiadomości. Spróbuj za chwilę." and
    does **not** consume a rate-limit slot.
  - `console`: logs subject + masked recipient + the links, and keeps the last
    50 messages in memory; `GET /api/dev/outbox` returns them **only** when
    `EMAIL_BACKEND=console` and `AUTH_DISABLED` is false (e2e) — 404 otherwise.
- Settings: `EMAIL_BACKEND` (default `console`), `RESEND_API_KEY`, `EMAIL_FROM`,
  `EMAIL_REPLY_TO`, `PUBLIC_BASE_URL` (absolute links; default `https://omj-validator.pl`), `TERMS_VERSION`.
- Templates: Jinja2, `templates/email/*.html` + `*.txt`, one shared layout.
  Email-safe HTML: table layout, inline styles, 600 px max, system font stack,
  bulletproof buttons, no external CSS, no data-URI images; the logo is
  `<img src="{PUBLIC_BASE_URL}/images/logo-email.png" width=... alt="OMJ Validator">`.
  Plain-text part always present. Polish, `lang="pl"`.
- `scripts/render_email_previews.py` writes every template with sample data to
  `tmp/email-previews/*.html` for review.
- Never log message bodies or full addresses (`app/privacy.py::mask_email`).
- Telegram notifications: none for these events (keep personal data off Telegram).

## Retention (`app/retention.py`, daily pass)

- `pending_parent` accounts with `pending_since` older than 14 days → full erasure.
- `email_tokens` 30 days after `expires_at`; `login_failures` after 24 h.
- `parents` with no children → deleted (also enforced on every child deletion).

## Documents

- `/regulamin` (`frontend/src/app/regulamin/page.tsx`): age step, parent
  consent by e-mail and what the parent receives, login accounts (what we store:
  login, password hash, year of birth, parent e-mail), parent rights and the
  parent page, the 14-day rule, Resend as a processor (sending e-mail; EU sending
  region; US company certified under the EU–US Data Privacy Framework), new
  retention lines; bump `LAST_UPDATED` and `TERMS_VERSION` together.
- `docs/rodo/dpia.md`: data inventory (year of birth, parent e-mail, login,
  password hash, consent records), Resend as a recipient, residual risk "a child
  can type a second address of their own as the parent's" (accepted as
  proportionate per EDPB 05/2020), brute-force and account-recovery risks with
  their measures.
- `docs/rodo/README.md`: retention list.
- `CLAUDE.md`: new tables, env vars, routes.

## Testing

Targeted pytest for: migration (up on a DB with existing users keeps ids and FKs),
age arithmetic (incl. the 16-this-year case), registration both paths, pending
guard on every write router (one parametrised test over the route table, so a
new endpoint without the guard fails), consent accept / decline / expired /
reused token, GET never mutates, rate limits, password rules, login lockout and
generic errors, reset flow and `session_version`, legacy session compatibility,
retention passes, outbox endpoint 404 unless console+e2e. One Playwright e2e:
child registers with login/password → pending screen → link from
`/api/dev/outbox` → parent confirms → child's pending screen flips to active →
submits nothing but sees the normal app; plus decline path.
