"""控制流与架构抽象模式。"""

from app.services.figures.compiler.patterns.dependency import apply_dependencies
from app.services.figures.compiler.patterns.interrupt import apply_interrupt_branches
from app.services.figures.compiler.patterns.optional import apply_optional_branches

__all__ = ["apply_dependencies", "apply_optional_branches", "apply_interrupt_branches"]
