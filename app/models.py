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


class Submission(BaseModel):
    id: str
    year: str
    etap: str
    task_number: int
    timestamp: datetime
    images: list[str]  # paths to uploaded images
    score: int
    feedback: str


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
