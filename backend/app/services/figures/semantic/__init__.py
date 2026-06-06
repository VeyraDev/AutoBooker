"""富 Semantic IR 层。"""

from app.services.figures.semantic.extractor import extract_semantic_ir
from app.services.figures.semantic.schema import SemanticIR

__all__ = ["SemanticIR", "extract_semantic_ir"]
