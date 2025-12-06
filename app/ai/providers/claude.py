"""Claude CLI provider implementation."""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Optional

from ...config import settings
from ...models import SubmissionResult
from ..parsing import parse_ai_response


class ClaudeProvider:
    """AI provider using Claude CLI for solution analysis."""

    def _load_prompt(self) -> str:
        """Load system prompt from file."""
        with open(settings.system_prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_timeout(self) -> int:
        """Return timeout in seconds for Claude CLI."""
        return settings.claude_timeout

    async def analyze_solution(
        self,
        task_pdf_path: Path,
        solution_pdf_path: Optional[Path],
        image_paths: list[Path],
        task_number: int,
    ) -> SubmissionResult:
        """
        Analyze a student's solution using Claude CLI.

        Args:
            task_pdf_path: Path to the task PDF
            solution_pdf_path: Path to the official solution PDF (for reference)
            image_paths: Paths to uploaded images of student's solution
            task_number: The task number (1-5)

        Returns:
            SubmissionResult with score and feedback
        """
        # Build the prompt - explicitly instruct Claude to read files
        prompt_parts = [
            self._load_prompt(),
            f"\n\n## Zadanie {task_number}\n",
            f"PRZECZYTAJ plik PDF z treścią zadania: {task_pdf_path}\n",
            f"Znajdź 'Zadanie {task_number}.' w dokumencie.\n",
        ]

        if solution_pdf_path and solution_pdf_path.exists():
            prompt_parts.append(
                f"\nPRZECZYTAJ oficjalne rozwiązanie (TYLKO do weryfikacji, NIE pokazuj uczniowi): {solution_pdf_path}\n"
            )

        prompt_parts.append("\n## Rozwiązanie ucznia\n")
        prompt_parts.append("PRZECZYTAJ poniższe zdjęcia z rozwiązaniem ucznia:\n")
        for i, img_path in enumerate(image_paths, 1):
            prompt_parts.append(f"- Zdjęcie {i}: {img_path}\n")

        prompt_parts.append(
            "\nPo przeczytaniu wszystkich plików, oceń rozwiązanie i odpowiedz w formacie JSON."
        )

        full_prompt = "".join(prompt_parts)

        # Write prompt to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(full_prompt)
            prompt_file = f.name

        try:
            # Build command with permissions for tasks/ and uploads/ directories
            cmd = (
                f'cat "{prompt_file}" | {settings.claude_path} '
                f"--print --output-format json --model {settings.claude_model} "
                f'--allowedTools "Read(**/*)" '
                f'--add-dir "{settings.tasks_dir}" --add-dir "{settings.uploads_dir}"'
            )

            # Execute
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(settings.base_dir),
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.get_timeout()
            )

            if proc.returncode != 0:
                return SubmissionResult(
                    score=0,
                    feedback=f"Błąd podczas analizy rozwiązania. Spróbuj ponownie później. (Kod: {proc.returncode})",
                )

            # Parse response using shared utility
            response_text = stdout.decode("utf-8", errors="replace")
            return self._parse_response(response_text)

        except asyncio.TimeoutError:
            # Kill the subprocess to prevent zombie processes
            try:
                proc.kill()
            except Exception:
                pass
            try:
                await proc.wait()
            except Exception:
                pass
            return SubmissionResult(
                score=0,
                feedback="Przekroczono limit czasu analizy. Spróbuj ponownie lub prześlij mniej zdjęć.",
            )
        except Exception as e:
            return SubmissionResult(
                score=0,
                feedback=f"Wystąpił nieoczekiwany błąd: {str(e)}",
            )
        finally:
            # Clean up temp file
            Path(prompt_file).unlink(missing_ok=True)

    def _parse_response(self, response_text: str) -> SubmissionResult:
        """Parse Claude CLI JSON response to extract score and feedback."""
        try:
            # Claude CLI returns JSON with result field
            response_data = json.loads(response_text)

            # Extract the actual content from Claude's response
            result_text = ""
            if "result" in response_data:
                result_text = response_data["result"]
            elif "content" in response_data:
                result_text = response_data["content"]
            else:
                result_text = response_text

            # Use shared parsing utility
            return parse_ai_response(result_text)

        except json.JSONDecodeError:
            # If Claude's wrapper JSON is malformed, try parsing raw text
            return parse_ai_response(response_text)
        except Exception as e:
            return SubmissionResult(
                score=0,
                feedback=f"Błąd przetwarzania: {str(e)}",
            )
