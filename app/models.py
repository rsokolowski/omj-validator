from pydantic import BaseModel, computed_field, Field
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
    title: str
    content: str
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
    year: str
    etap: str
    task_number: int
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
    year: str
    etap: str
    task_number: int
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
