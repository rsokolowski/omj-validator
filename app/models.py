from pydantic import BaseModel, computed_field, Field, field_validator
from datetime import datetime
from typing import Optional, Literal
from enum import Enum


class TaskCategory(str, Enum):
    """Mathematical categories for OMJ tasks."""
    ALGEBRA = "algebra"  # Systems of equations, algebraic identities, inequalities
    GEOMETRIA = "geometria"  # Plane geometry: triangles, quadrilaterals, circles
    TEORIA_LICZB = "teoria_liczb"  # Divisibility, primes, digits, diophantine equations
    KOMBINATORYKA = "kombinatoryka"  # Counting, existence, pigeonhole, tournaments
    LOGIKA = "logika"  # Weighing problems, grids, game theory, strategy
    ARYTMETYKA = "arytmetyka"  # Averages, ratios, basic calculations


class HintLevel(str, Enum):
    """Progressive hint levels based on Pólya's problem-solving method."""
    # Level 1: Help understand/reframe the problem (metacognitive)
    ZROZUMIENIE = "zrozumienie"
    # Level 2: Suggest general approach/strategy
    STRATEGIA = "strategia"
    # Level 3: Point toward key insight/direction
    KIERUNEK = "kierunek"
    # Level 4: Specific guidance without giving solution
    WSKAZOWKA = "wskazowka"


class IssueType(str, Enum):
    """Type of issue detected in a submission by abuse detection."""
    NONE = "none"              # No issues detected - normal submission
    WRONG_TASK = "wrong_task"  # Student submitted solution to different task
    INJECTION = "injection"    # Prompt injection attempt detected


class TaskPdf(BaseModel):
    """PDF file paths for a task (shared across tasks in same etap)."""
    tasks: str  # Path to tasks PDF
    solutions: Optional[str] = None  # Path to solutions PDF
    statistics: Optional[str] = None  # Path to statistics PDF


class TaskInfo(BaseModel):
    year: str
    etap: str
    number: int
    # Statement of the task (title + content) as printed in the OMJ PDF.
    # This text belongs to the competition organiser and is NOT part of the
    # repository - it is generated locally by fix_latex_content.py into
    # data/task_content/. When it has not been generated, `content` is None and
    # `title` falls back to "Zadanie {number}" (see app/storage.py); clients
    # should then link to the task PDF instead of rendering the statement.
    title: str
    content: Optional[str] = None
    pdf: TaskPdf
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)  # 1=easy, 5=very hard
    categories: list[str] = []  # Values from TaskCategory enum
    # Progressive hints (4 levels based on Pólya's method):
    # [0] zrozumienie - help understand/reframe problem
    # [1] strategia - suggest general approach
    # [2] kierunek - point to key insight
    # [3] wskazowka - specific guidance (not solution)
    hints: list[str] = []
    # Prerequisites: list of task keys (e.g., ["2020_etap1_3", "2021_etap2_1"])
    # Task is "unlocked" when all prerequisites are mastered
    prerequisites: list[str] = []
    # Skills needed to solve this task
    skills_required: list[str] = []
    # Skills developed by mastering this task
    skills_gained: list[str] = []

    @computed_field
    @property
    def has_content(self) -> bool:
        """True when the locally generated statement is available."""
        return bool(self.content and self.content.strip())

    @computed_field
    @property
    def has_solution(self) -> bool:
        return self.pdf.solutions is not None

    @computed_field
    @property
    def has_statistics(self) -> bool:
        return self.pdf.statistics is not None


class TaskStats(BaseModel):
    submission_count: int = 0
    highest_score: int = 0


class SubmissionResult(BaseModel):
    score: int
    feedback: str
    issue_type: IssueType = IssueType.NONE  # Abuse detection result
    abuse_score: int = 0  # 0-100 confidence in abuse detection
    scoring_meta: Optional[dict] = None  # LLM metadata (model, tokens, cost, timing)


class SubmissionStatus(str, Enum):
    """Status of a submission through the processing pipeline."""
    PENDING = "pending"          # Uploaded, awaiting processing
    PROCESSING = "processing"    # Being analyzed by AI
    COMPLETED = "completed"      # Successfully scored
    FAILED = "failed"            # Processing failed


class Submission(BaseModel):
    """Student solution submission with AI scoring."""
    id: str
    user_id: str  # Google sub of the user who submitted
    # OMJ task reference - all three are None for a private task submission
    year: Optional[str] = None
    etap: Optional[str] = None
    task_number: Optional[int] = None
    # Set instead of the OMJ fields for a private task submission
    private_task_id: Optional[str] = None
    hints_used: int = 0
    timestamp: datetime
    status: SubmissionStatus = SubmissionStatus.COMPLETED
    images: list[str]  # paths to uploaded images (relative to uploads_dir)
    score: Optional[int] = None  # Null if failed
    feedback: Optional[str] = None  # Null if failed
    error_message: Optional[str] = None  # Set if status is FAILED
    issue_type: IssueType = IssueType.NONE  # Abuse detection result
    abuse_score: int = 0  # 0-100 confidence in abuse detection
    scoring_meta: Optional[dict] = None  # LLM metadata (model, tokens, cost, timing)


class LoginRequest(BaseModel):
    key: str
    remember: bool = False


class SubmitRequest(BaseModel):
    year: str
    etap: str
    task_number: int


# Progress tracking models
class TaskStatus(str, Enum):
    """Task completion status for progression graph."""
    LOCKED = "locked"        # Prerequisites not met
    UNLOCKED = "unlocked"    # Ready to attempt (all prerequisites mastered)
    MASTERED = "mastered"    # Score meets threshold (etap2: >=5, etap1: >=2)


class GraphNode(BaseModel):
    """Node in the progression graph representing a task."""
    key: str                    # e.g., "2024_etap1_3"
    year: str
    etap: str
    number: int
    title: str
    difficulty: Optional[int] = None
    categories: list[str] = []
    prerequisites: list[str] = []
    status: TaskStatus
    best_score: int = 0


class GraphEdge(BaseModel):
    """Edge in the progression graph (prerequisite relationship)."""
    source: str  # Prerequisite task key
    target: str  # Dependent task key


class ProgressData(BaseModel):
    """Complete progression data for the progress page."""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    recommendations: list[GraphNode]
    stats: dict  # {total, mastered, unlocked, locked}


class SkillCategoryInfo(BaseModel):
    """Skill category metadata from skills.json."""
    id: str
    name: str
    description: str


class SkillInfo(BaseModel):
    """Skill information from skills.json."""
    id: str
    name: str
    category: str  # Category ID (e.g., "number_theory")
    description: str
    examples: list[str] = []


class PrerequisiteStatus(BaseModel):
    """Prerequisite task with mastery status for display."""
    key: str  # e.g., "2023_etap1_2"
    year: str
    etap: str
    number: int
    title: str
    status: Literal["mastered", "in_progress"] | None = None  # None for unauthenticated users
    url: str  # e.g., "/task/2023/etap1/2"


# ==================== User Submissions (Moje rozwiązania) ====================


class UserSubmissionStats(BaseModel):
    """Aggregate statistics for user's submissions."""
    total_submissions: int
    completed_count: int
    failed_count: int
    pending_count: int
    avg_score: Optional[float] = None  # Average of completed submissions
    best_score: Optional[int] = None
    tasks_attempted: int  # Unique tasks with at least one submission
    tasks_mastered: int  # Unique tasks with score >= mastery threshold


class UserSubmissionListItem(BaseModel):
    """Single submission item for user's submission list."""
    id: str
    # OMJ task reference, or None for a private task (then private_task_id)
    year: Optional[str] = None
    etap: Optional[str] = None
    task_number: Optional[int] = None
    private_task_id: Optional[str] = None
    task_title: str
    task_categories: list[str]
    timestamp: datetime
    status: SubmissionStatus
    score: Optional[int] = None
    max_score: int  # Based on etap (3 for etap1, 6 for etap2/3)
    feedback: Optional[str] = None
    feedback_preview: Optional[str] = None  # First ~150 chars of feedback
    error_message: Optional[str] = None
    images: list[str] = []


class UserSubmissionsResponse(BaseModel):
    """Paginated response for user's submissions with stats."""
    submissions: list[UserSubmissionListItem]
    stats: UserSubmissionStats
    total_count: int
    offset: int
    limit: int
    has_more: bool


# ==================== Account deletion (RODO art. 17) ====================


# Exact phrase the user must type to confirm erasure. Kept ASCII-only so it can
# be typed on any keyboard, and shown verbatim in the UI dialog.
ACCOUNT_DELETE_CONFIRMATION = "USUWAM KONTO"


class DeleteAccountRequest(BaseModel):
    """Body of POST /api/account/delete - guards against accidental calls."""
    confirmation: str


class DeleteAccountResponse(BaseModel):
    """What was actually erased, so the UI can confirm it to the user."""
    success: bool
    deleted_submissions: int
    deleted_files: int


# ==================== Private tasks (Moje zadania) ====================


PRIVATE_TASK_CATEGORIES = {c.value for c in TaskCategory}


class ExtractedProblem(BaseModel):
    """One problem the AI read off a photo - a draft, not yet a task."""
    label: str  # the number as printed, e.g. "Zadanie 3"
    title: str
    content: str
    category: Optional[str] = None
    difficulty: Optional[int] = None


class PrivateExtractionResult(BaseModel):
    is_math_problem: bool
    abuse_score: int = 0
    problems: list[ExtractedProblem] = []
    meta: dict = {}  # model, tokens, cost - no content


class PrivateTaskMeta(BaseModel):
    hints: list[str] = []
    category: Optional[str] = None
    difficulty: Optional[int] = None
    abuse_score: int = 0
    meta: dict = {}


PRIVATE_TITLE_MAX = 120
PRIVATE_CONTENT_MIN = 20
PRIVATE_CONTENT_MAX = 10_000
PRIVATE_SOURCE_LABEL_MAX = 120
PRIVATE_TASKS_PER_REQUEST = 8


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


class PrivateTaskInput(BaseModel):
    """One task to create - text the student confirmed or typed."""
    title: str = Field(min_length=1, max_length=PRIVATE_TITLE_MAX)
    content: str = Field(min_length=PRIVATE_CONTENT_MIN, max_length=PRIVATE_CONTENT_MAX)
    source_label: Optional[str] = Field(default=None, max_length=PRIVATE_SOURCE_LABEL_MAX)
    category: Optional[str] = None
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)

    @field_validator("title", "content", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("source_label", mode="before")
    @classmethod
    def _blank_label_is_none(cls, value):
        return _clean_optional_text(value) if isinstance(value, str) else value

    @field_validator("category")
    @classmethod
    def _known_category(cls, value):
        if value is not None and value not in PRIVATE_TASK_CATEGORIES:
            raise ValueError("Nieznana kategoria")
        return value


class CreatePrivateTasksRequest(BaseModel):
    # Draft from POST /api/private-tasks/extract; absent for a typed task
    draft_id: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    tasks: list[PrivateTaskInput] = Field(min_length=1, max_length=PRIVATE_TASKS_PER_REQUEST)


class UpdatePrivateTaskRequest(BaseModel):
    """PATCH body - only the fields present are changed."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=PRIVATE_TITLE_MAX)
    content: Optional[str] = Field(
        default=None, min_length=PRIVATE_CONTENT_MIN, max_length=PRIVATE_CONTENT_MAX
    )
    # "" clears the label
    source_label: Optional[str] = Field(default=None, max_length=PRIVATE_SOURCE_LABEL_MAX)
    category: Optional[str] = None
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)

    @field_validator("title", "content", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("category")
    @classmethod
    def _known_category(cls, value):
        if value is not None and value not in PRIVATE_TASK_CATEGORIES:
            raise ValueError("Nieznana kategoria")
        return value
