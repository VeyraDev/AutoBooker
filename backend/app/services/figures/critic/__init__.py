"""配图 Critic 层。"""

from app.services.figures.critic.layout_critic import run_layout_critic
from app.services.figures.critic.semantic import run_semantic_llm_critic
from app.services.figures.critic.structural import run_structural_critic

__all__ = ["run_structural_critic", "run_layout_critic", "run_semantic_llm_critic"]
