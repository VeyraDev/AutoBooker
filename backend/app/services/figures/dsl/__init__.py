"""DiagramDSL 构建与转换。"""

from app.services.figures.dsl.defaults import default_dsl_for_type
from app.services.figures.dsl.from_parsed_spec import build_dsl_from_parsed
from app.services.figures.dsl.to_parsed_spec import dsl_to_parsed_spec

__all__ = [
    "build_dsl_from_parsed",
    "dsl_to_parsed_spec",
    "default_dsl_for_type",
]
