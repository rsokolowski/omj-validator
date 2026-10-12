"use client";

import { FormEvent, useState } from "react";
import { Alert, Box, Link as MuiLink, Typography } from "@mui/material";
import { APIError } from "@/lib/api/client";
import { accountApi, errorText } from "@/lib/api/account";
import {
  emailProblem,
  isAmbiguousBirthYear,
  isUnder16,
  normalizeEmail,
} from "@/lib/utils/account";
import { FormCard } from "./FormCard";
import { StepHeading } from "./StepHeading";
import { StepProgress } from "./StepProgress";
import { StepActions } from "./StepActions";
import { SubmitButton } from "./SubmitButton";
import { BirthYearFields } from "./BirthYearFields";
import { ParentEmailField } from "./ParentEmailField";
import { TermsCheckbox } from "./TermsCheckbox";

type Step = "year" | "final";
type Field = "birth_year" | "turned_16" | "parent_email" | "accept_terms";
type Errors = Partial<Record<Field, string>>;

const STEP_OF_FIELD: Record<Field, Step> = {
  birth_year: "year",
  turned_16: "year",
  parent_email: "final",
  accept_terms: "final",
};

interface CompleteProfileProps {
  currentYear: number;
  /** Adres konta Google - adres rodzica musi byc inny */
  ownEmail: string | null;
}

/** Krok wieku dla kont zalozonych, zanim o niego pytalismy. */
export function CompleteProfile({ currentYear, ownEmail }: CompleteProfileProps) {
  const [step, setStep] = useState<Step>("year");
  const [moved, setMoved] = useState(false);
  const [birthYear, setBirthYear] = useState<number | null>(null);
  const [turned16, setTurned16] = useState<boolean | null>(null);
  const [parentEmail, setParentEmail] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const under16 = isUnder16(birthYear, turned16, currentYear);

  const clearError = (field: Field) =>
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });

  const goTo = (target: Step) => {
    setFormError(null);
    setMoved(true);
    setStep(target);
  };

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
    goTo("final");
  };

  const submitFinal = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting || birthYear === null) return;
    const email = normalizeEmail(parentEmail);
    if (under16) {
      const problem = emailProblem(email);
      if (problem) {
        setErrors((prev) => ({ ...prev, parent_email: problem }));
        return;
      }
      if (ownEmail && email === normalizeEmail(ownEmail)) {
        setErrors((prev) => ({
          ...prev,
          parent_email: "To adres Twojego konta. Wpisz adres e-mail rodzica lub opiekuna.",
        }));
        return;
      }
    } else if (!acceptTerms) {
      setErrors((prev) => ({ ...prev, accept_terms: "Zaznacz zgodę, żeby korzystać z serwisu." }));
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const result = await accountApi.completeProfile({
        birth_year: birthYear,
        ...(isAmbiguousBirthYear(birthYear, currentYear) && turned16 !== null ? { turned_16: turned16 } : {}),
        ...(under16 ? { parent_email: email } : { accept_terms: true }),
      });
      window.location.href = result.redirect;
    } catch (error) {
      setSubmitting(false);
      if (error instanceof APIError) {
        if (error.code === "already_done" && typeof error.body?.redirect === "string") {
          window.location.href = error.body.redirect;
          return;
        }
        if (error.field && error.field in STEP_OF_FIELD) {
          const field = error.field as Field;
          setErrors((prev) => ({ ...prev, [field]: error.message }));
          if (STEP_OF_FIELD[field] !== step) goTo(STEP_OF_FIELD[field]);
          return;
        }
      }
      setFormError(errorText(error));
    }
  };

  return (
    <FormCard>
      <StepProgress step={step === "year" ? 1 : 2} total={2} />

      {step === "year" && (
        <Box component="form" noValidate onSubmit={submitYear} key="year">
          <StepHeading focus={moved}>Uzupełnij jedną informację</StepHeading>
          <Typography sx={{ color: "grey.700", mb: 3 }}>
            Od teraz pytamy wszystkich o rok urodzenia, bo osoby poniżej 16 lat potrzebują zgody
            rodzica. To zajmie chwilę.
          </Typography>
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

      {step === "final" && (
        <Box component="form" noValidate onSubmit={submitFinal} key="final">
          {under16 ? (
            <>
              <StepHeading focus={moved}>Podaj adres e-mail rodzica lub opiekuna</StepHeading>
              <Typography sx={{ color: "grey.700", mb: 2 }}>
                Wyślemy rodzicowi prośbę o zgodę. Bez niej nie prześlesz nowych rozwiązań.
              </Typography>
              <Alert severity="info" sx={{ mb: 3 }}>
                Twoje dotychczasowe rozwiązania zostają. Dopóki rodzic nie potwierdzi konta, możesz
                je przeglądać, ale nie prześlesz nowych. Jeśli rodzic nie zgodzi się w ciągu 14 dni,
                konto zostanie usunięte razem ze wszystkimi danymi.
              </Alert>
              <ParentEmailField
                value={parentEmail}
                onChange={(value) => {
                  setParentEmail(value);
                  clearError("parent_email");
                }}
                error={errors.parent_email}
                disabled={submitting}
              />
            </>
          ) : (
            <>
              <StepHeading focus={moved}>Ostatni krok: zasady serwisu</StepHeading>
              <Typography sx={{ color: "grey.700", mb: 2.5 }}>
                Masz już 16 lat, więc nie potrzebujesz zgody rodzica. Potrzebujemy za to Twojej
                wyraźnej zgody — zaznacz ją poniżej.
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

          <Box aria-live="assertive">
            {formError && (
              <Alert severity="error" sx={{ mt: 2.5 }}>
                {formError}
              </Alert>
            )}
          </Box>

          <StepActions onBack={() => goTo("year")} backDisabled={submitting}>
            <SubmitButton busy={submitting} busyLabel="Zapisywanie…">
              {under16 ? "Wyślij prośbę do rodzica" : "Zapisz"}
            </SubmitButton>
          </StepActions>
        </Box>
      )}

      <Typography variant="body2" sx={{ mt: 4, pt: 2, borderTop: 1, borderColor: "grey.200", color: "grey.600" }}>
        Nie chcesz teraz?{" "}
        {/* Zwykly <a>: prefetch Next.js wylogowalby uzytkownika */}
        <MuiLink href="/logout" sx={{ color: "primary.main" }}>
          Wyloguj się
        </MuiLink>
      </Typography>
    </FormCard>
  );
}
