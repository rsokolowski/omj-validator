"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Link as MuiLink,
  TextField,
  Typography,
} from "@mui/material";
import GoogleIcon from "@mui/icons-material/Google";
import KeyIcon from "@mui/icons-material/Key";
import ChevronRight from "@mui/icons-material/ChevronRight";
import CheckCircle from "@mui/icons-material/CheckCircle";
import { APIError } from "@/lib/api/client";
import { accountApi, errorText } from "@/lib/api/account";
import {
  isAmbiguousBirthYear,
  isUnder16,
  loginProblem,
  normalizeEmail,
  emailProblem,
  normalizeLogin,
  passwordProblem,
} from "@/lib/utils/account";
import { FormCard } from "./FormCard";
import { StepHeading } from "./StepHeading";
import { StepProgress } from "./StepProgress";
import { StepActions } from "./StepActions";
import { SubmitButton } from "./SubmitButton";
import { BirthYearFields } from "./BirthYearFields";
import { PasswordField } from "./PasswordField";
import { ParentEmailField } from "./ParentEmailField";
import { TermsCheckbox } from "./TermsCheckbox";
import { GoogleButton } from "./GoogleButton";

type Step = "year" | "method" | "credentials" | "final";
type Method = "google" | "login";
type Field = "birth_year" | "turned_16" | "login" | "password" | "parent_email" | "accept_terms";
type Errors = Partial<Record<Field, string>>;

const STEP_OF_FIELD: Record<Field, Step> = {
  birth_year: "year",
  turned_16: "year",
  login: "credentials",
  password: "credentials",
  parent_email: "final",
  accept_terms: "final",
};

const SAME_ADDRESS_ERROR = "To adres Twojego konta Google. Wpisz adres e-mail rodzica lub opiekuna.";

type LoginCheck =
  | { state: "idle" }
  | { state: "checking"; login: string }
  | { state: "available"; login: string }
  | { state: "taken"; login: string; message: string };

type GoogleIdentity =
  | { state: "loading" }
  | { state: "ready"; email: string }
  | { state: "expired" }
  | { state: "error"; message: string };

interface RegistrationWizardProps {
  currentYear: number;
  /** ?google=1 - the child came back from Google without an account */
  googleMode: boolean;
  /** ?blad=ten-sam-adres - the parent's address was the child's own Google address */
  sameAddressError: boolean;
}

export function RegistrationWizard({ currentYear, googleMode, sameAddressError }: RegistrationWizardProps) {
  const [step, setStep] = useState<Step>("year");
  // Fokus na naglowek dopiero po pierwszym przejsciu, nie przy wejsciu na strone
  const [moved, setMoved] = useState(false);
  const [birthYear, setBirthYear] = useState<number | null>(null);
  const [turned16, setTurned16] = useState<boolean | null>(null);
  const [method, setMethod] = useState<Method | null>(googleMode ? "google" : null);
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [loginCheck, setLoginCheck] = useState<LoginCheck>({ state: "idle" });
  const [parentEmail, setParentEmail] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [errors, setErrors] = useState<Errors>(
    sameAddressError ? { parent_email: SAME_ADDRESS_ERROR } : {}
  );
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [google, setGoogle] = useState<GoogleIdentity>(
    googleMode ? { state: "loading" } : { state: "expired" }
  );

  useEffect(() => {
    if (!googleMode) return;
    let cancelled = false;
    accountApi
      .registrationState()
      .then((data) => {
        if (cancelled) return;
        setGoogle(data.google ? { state: "ready", email: data.google.email } : { state: "expired" });
      })
      .catch((error) => {
        if (!cancelled) setGoogle({ state: "error", message: errorText(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [googleMode]);

  const under16 = isUnder16(birthYear, turned16, currentYear);
  const needsParent = method === "login" || under16 === true;
  const googleIdentity = google.state === "ready" ? google.email : null;

  const steps: Step[] = googleMode
    ? ["year", "final"]
    : method === "google"
      ? ["year", "method", "final"]
      : ["year", "method", "credentials", "final"];
  const stepIndex = steps.indexOf(step);

  const clearError = (field: Field) => {
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const goTo = (target: Step) => {
    setFormError(null);
    setMoved(true);
    setStep(target);
  };

  const goBack = () => {
    if (stepIndex > 0) goTo(steps[stepIndex - 1]);
  };

  // ---------------------------------------------------------------- step 1: year

  const submitYear = (e: FormEvent) => {
    e.preventDefault();
    if (birthYear === null) {
      setErrors((prev) => ({ ...prev, birth_year: "Wybierz rok urodzenia z listy." }));
      return;
    }
    if (isAmbiguousBirthYear(birthYear, currentYear) && turned16 === null) {
      setErrors((prev) => ({ ...prev, turned_16: "Zaznacz jedną odpowiedź." }));
      return;
    }
    goTo(googleMode ? "final" : "method");
  };

  // ---------------------------------------------------------------- step 2: method

  const chooseMethod = (chosen: Method) => {
    setMethod(chosen);
    goTo(chosen === "login" ? "credentials" : "final");
  };

  // ---------------------------------------------------------------- step 3: login + password

  const checkLogin = async () => {
    const normalized = normalizeLogin(login);
    if (!normalized) return;
    const problem = loginProblem(normalized);
    if (problem) {
      setErrors((prev) => ({ ...prev, login: problem }));
      return;
    }
    if (loginCheck.state !== "idle" && loginCheck.login === normalized) return;
    setLoginCheck({ state: "checking", login: normalized });
    try {
      const result = await accountApi.loginAvailable(normalized);
      if (result.available) {
        setLoginCheck({ state: "available", login: result.login });
      } else {
        const message = result.message || "Ten login jest zajęty. Wymyśl inny.";
        setLoginCheck({ state: "taken", login: result.login, message });
        setErrors((prev) => ({ ...prev, login: message }));
      }
    } catch {
      // Limit sprawdzen albo brak sieci - serwer i tak sprawdzi login przy zapisie
      setLoginCheck({ state: "idle" });
    }
  };

  const submitCredentials = (e: FormEvent) => {
    e.preventDefault();
    const normalized = normalizeLogin(login);
    const next: Errors = {};
    const loginError =
      loginProblem(normalized) ||
      (loginCheck.state === "taken" && loginCheck.login === normalized ? loginCheck.message : null);
    if (loginError) next.login = loginError;
    const passwordError = passwordProblem(password, normalized);
    if (passwordError) next.password = passwordError;
    if (next.login || next.password) {
      setErrors((prev) => ({ ...prev, ...next }));
      return;
    }
    goTo("final");
  };

  // ---------------------------------------------------------------- step 4: parent / terms, submit

  const handleApiError = (error: unknown) => {
    if (error instanceof APIError && error.field && error.field in STEP_OF_FIELD) {
      const field = error.field as Field;
      setErrors((prev) => ({ ...prev, [field]: error.message }));
      if (field === "login") setLoginCheck({ state: "idle" });
      const target = STEP_OF_FIELD[field];
      if (target !== step && steps.includes(target)) goTo(target);
      return;
    }
    setFormError(errorText(error));
  };

  const submitFinal = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting || birthYear === null) return;
    setFormError(null);

    const email = normalizeEmail(parentEmail);
    if (needsParent) {
      const problem = emailProblem(email);
      if (problem) {
        setErrors((prev) => ({ ...prev, parent_email: problem }));
        return;
      }
      if (googleIdentity && email === normalizeEmail(googleIdentity)) {
        setErrors((prev) => ({ ...prev, parent_email: SAME_ADDRESS_ERROR }));
        return;
      }
    } else if (!acceptTerms) {
      setErrors((prev) => ({ ...prev, accept_terms: "Zaznacz zgodę, żeby założyć konto." }));
      return;
    }

    const age = {
      birth_year: birthYear,
      ...(isAmbiguousBirthYear(birthYear, currentYear) && turned16 !== null ? { turned_16: turned16 } : {}),
    };

    setSubmitting(true);
    try {
      if (method === "login") {
        const result = await accountApi.registerLogin({
          ...age,
          login: normalizeLogin(login),
          password,
          parent_email: email,
        });
        window.location.href = result.redirect;
      } else {
        const result = await accountApi.registerGoogle(
          needsParent ? { ...age, parent_email: email } : { ...age, accept_terms: true }
        );
        window.location.href = result.redirect;
      }
      // Zostajemy w stanie "wysylanie" az przegladarka przejdzie na nowa strone
    } catch (error) {
      setSubmitting(false);
      handleApiError(error);
    }
  };

  // ---------------------------------------------------------------- render

  if (googleMode && google.state === "loading") {
    return (
      <FormCard>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, py: 2 }} role="status">
          <CircularProgress size={24} />
          <Typography>Sprawdzamy logowanie przez Google…</Typography>
        </Box>
      </FormCard>
    );
  }

  if (googleMode && google.state !== "ready") {
    return (
      <FormCard>
        <StepHeading focus={false}>
          {google.state === "error" ? "Nie udało się sprawdzić logowania" : "Zaloguj się jeszcze raz przez Google"}
        </StepHeading>
        {google.state === "error" ? (
          <Alert severity="error" sx={{ mb: 3 }}>
            {google.message}
          </Alert>
        ) : (
          <Typography sx={{ color: "grey.700", mb: 3 }}>
            Od logowania przez Google minęło ponad 10 minut, więc dla bezpieczeństwa musimy
            poprosić o nie jeszcze raz. Nic nie przepadło — zaloguj się i dokończ zakładanie konta.
          </Typography>
        )}
        <GoogleButton href="/login/google" />
        <Typography variant="body2" sx={{ mt: 3, color: "grey.700" }}>
          Albo{" "}
          <MuiLink href="/rejestracja" sx={{ color: "primary.main" }}>
            zacznij zakładanie konta od początku
          </MuiLink>
          .
        </Typography>
      </FormCard>
    );
  }

  const headingFocus = moved;

  return (
    <FormCard>
      <StepProgress step={stepIndex + 1} total={steps.length} />

      {googleIdentity && (
        <Alert severity="success" icon={<CheckCircle fontSize="inherit" />} sx={{ mb: 2.5 }}>
          Zalogowano przez Google jako <strong>{googleIdentity}</strong>. Odpowiedz jeszcze na{" "}
          {steps.length === 2 ? "dwa pytania" : "kilka pytań"}, a konto będzie gotowe.
        </Alert>
      )}

      {step === "year" && (
        <Box component="form" noValidate onSubmit={submitYear} key="year">
          <StepHeading focus={headingFocus}>Twój rok urodzenia</StepHeading>
          <Typography sx={{ color: "grey.700", mb: 3 }}>
            Pytamy, bo osoby poniżej 16 lat potrzebują zgody rodzica, żeby korzystać z serwisu.
          </Typography>
          {sameAddressError && (
            <Alert severity="warning" sx={{ mb: 3 }}>
              Adres rodzica musi być inny niż adres, którym logujesz się przez Google. Odpowiedz
              jeszcze raz na pytania i wpisz adres e-mail rodzica lub opiekuna.
            </Alert>
          )}
          <BirthYearFields
            currentYear={currentYear}
            birthYear={birthYear}
            turned16={turned16}
            onBirthYearChange={(year) => {
              setBirthYear(year);
              setTurned16(null);
              clearError("birth_year");
              clearError("turned_16");
            }}
            onTurned16Change={(value) => {
              setTurned16(value);
              clearError("turned_16");
            }}
            birthYearError={errors.birth_year}
            turned16Error={errors.turned_16}
          />
          <StepActions>
            <SubmitButton busy={false} busyLabel="">
              Dalej
            </SubmitButton>
          </StepActions>
        </Box>
      )}

      {step === "method" && (
        <Box key="method">
          <StepHeading focus={headingFocus}>Jak chcesz się logować?</StepHeading>
          <Typography sx={{ color: "grey.700", mb: 3 }}>Wybierz jedną z dwóch możliwości.</Typography>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
            <MethodOption
              icon={<GoogleIcon />}
              title="Mam konto Google"
              description="Zalogujesz się przez Google — nie musisz pamiętać kolejnego hasła."
              onClick={() => chooseMethod("google")}
            />
            <MethodOption
              icon={<KeyIcon />}
              title="Nie mam adresu e-mail"
              description="Wymyślisz login i hasło. Gdy zapomnisz hasła, pomoże Ci rodzic."
              onClick={() => chooseMethod("login")}
            />
          </Box>
          <StepActions onBack={goBack} />
        </Box>
      )}

      {step === "credentials" && (
        <Box component="form" noValidate onSubmit={submitCredentials} key="credentials">
          <StepHeading focus={headingFocus}>Wymyśl login i hasło</StepHeading>
          <Typography sx={{ color: "grey.700", mb: 3 }}>
            Będziesz ich używać przy każdym logowaniu. Zapisz je albo zapamiętaj.
          </Typography>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
            <TextField
              id="new-login"
              label="Login"
              value={login}
              onChange={(e) => {
                setLogin(e.target.value);
                clearError("login");
                setLoginCheck({ state: "idle" });
              }}
              onBlur={checkLogin}
              error={Boolean(errors.login)}
              helperText={
                errors.login ||
                (loginCheck.state === "available" && loginCheck.login === normalizeLogin(login)
                  ? "Ten login jest wolny."
                  : loginCheck.state === "checking"
                    ? "Sprawdzamy, czy login jest wolny…"
                    : "Nie używaj imienia i nazwiska. Możesz użyć liter (bez polskich znaków), cyfr oraz . _ -")
              }
              autoComplete="username"
              fullWidth
              slotProps={{
                htmlInput: { autoCapitalize: "none", autoCorrect: "off", spellCheck: false, maxLength: 32 },
                formHelperText: {
                  sx:
                    loginCheck.state === "available" && !errors.login
                      ? { color: "success.main", fontWeight: 500 }
                      : undefined,
                  // Wynik sprawdzenia loginu jest ogloszony czytnikowi ekranu
                  "aria-live": "polite",
                },
              }}
            />
            <PasswordField
              id="new-password"
              label="Hasło"
              value={password}
              onChange={(value) => {
                setPassword(value);
                clearError("password");
              }}
              autoComplete="new-password"
              error={errors.password}
              helperText="Co najmniej 8 znaków. Najłatwiej zapamiętać kilka słów, np. „zielony rower w lesie”."
            />
          </Box>
          <StepActions onBack={goBack}>
            <SubmitButton busy={false} busyLabel="">
              Dalej
            </SubmitButton>
          </StepActions>
        </Box>
      )}

      {step === "final" && (
        <Box component="form" noValidate onSubmit={submitFinal} key="final">
          {needsParent ? (
            <>
              <StepHeading focus={headingFocus}>Podaj adres e-mail rodzica lub opiekuna</StepHeading>
              <Typography sx={{ color: "grey.700", mb: 1 }}>
                Wyślemy rodzicowi prośbę o zgodę. Dopóki jej nie da, możesz przeglądać zadania,
                ale nie prześlesz jeszcze rozwiązań.
              </Typography>
              {method === "login" && (
                <Typography sx={{ color: "grey.700", mb: 1 }}>
                  Na ten adres trafi też link do zmiany hasła, gdyby kiedyś wypadło Ci z głowy.
                </Typography>
              )}
              <Box sx={{ mt: 2.5 }}>
                <ParentEmailField
                  value={parentEmail}
                  onChange={(value) => {
                    setParentEmail(value);
                    clearError("parent_email");
                  }}
                  error={errors.parent_email}
                  disabled={submitting}
                />
              </Box>
            </>
          ) : (
            <>
              <StepHeading focus={headingFocus}>Ostatni krok: zasady serwisu</StepHeading>
              <Typography sx={{ color: "grey.700", mb: 2.5 }}>
                Masz już 16 lat, więc nie potrzebujesz zgody rodzica. Przeczytaj regulamin —
                wyjaśniamy w nim, co dzieje się z Twoimi rozwiązaniami.
              </Typography>
              <TermsCheckbox
                checked={acceptTerms}
                onChange={(checked) => {
                  setAcceptTerms(checked);
                  clearError("accept_terms");
                }}
                error={errors.accept_terms}
                disabled={submitting}
              />
            </>
          )}

          {method === "google" && !googleIdentity && (
            <Typography variant="body2" sx={{ color: "grey.600", mt: 2.5 }}>
              Po kliknięciu przeniesiemy Cię do Google, żeby wybrać konto.
            </Typography>
          )}

          <Box aria-live="assertive">
            {formError && (
              <Alert severity="error" sx={{ mt: 2.5 }}>
                {formError}
              </Alert>
            )}
          </Box>

          <StepActions onBack={stepIndex > 0 ? goBack : undefined} backDisabled={submitting}>
            <SubmitButton
              busy={submitting}
              busyLabel={method === "google" && !googleIdentity ? "Przechodzimy do Google…" : "Zakładamy konto…"}
            >
              {method === "google" && !googleIdentity ? "Dalej: wybierz konto Google" : "Załóż konto"}
            </SubmitButton>
          </StepActions>
        </Box>
      )}

      <Typography variant="body2" sx={{ mt: 4, pt: 2.5, borderTop: 1, borderColor: "grey.200", color: "grey.700" }}>
        Masz już konto?{" "}
        <MuiLink component={Link} href="/login" sx={{ color: "primary.main", fontWeight: 500 }}>
          Zaloguj się
        </MuiLink>
      </Typography>
    </FormCard>
  );
}

interface MethodOptionProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}

/** Duzy przycisk-karta wyboru (cel dotyku na cala szerokosc). */
function MethodOption({ icon, title, description, onClick }: MethodOptionProps) {
  return (
    <Button
      variant="outlined"
      onClick={onClick}
      fullWidth
      sx={{
        justifyContent: "flex-start",
        textAlign: "left",
        gap: { xs: 1.5, sm: 2 },
        p: { xs: 1.5, sm: 2 },
        borderColor: "grey.300",
        color: "grey.900",
        "&:hover": { borderColor: "primary.main", bgcolor: "#eff6ff" },
      }}
    >
      <Box
        component="span"
        aria-hidden="true"
        sx={{
          display: "inline-flex",
          p: 1,
          borderRadius: 2,
          bgcolor: "#eff6ff",
          color: "primary.main",
          flexShrink: 0,
        }}
      >
        {icon}
      </Box>
      <Box component="span" sx={{ display: "flex", flexDirection: "column", flex: 1 }}>
        <Box component="span" sx={{ fontWeight: 600, fontSize: "1rem", lineHeight: 1.4, mb: 0.25 }}>
          {title}
        </Box>
        <Box component="span" sx={{ color: "grey.600", fontSize: "0.875rem", fontWeight: 400, lineHeight: 1.5 }}>
          {description}
        </Box>
      </Box>
      <ChevronRight aria-hidden="true" sx={{ color: "grey.500", flexShrink: 0, display: { xs: "none", sm: "block" } }} />
    </Button>
  );
}
