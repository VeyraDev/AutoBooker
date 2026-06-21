# HTML Template Renderer

This package keeps the legacy deterministic HTML/SVG-compatible renderer. New
structural figures should prefer the generic compositor route; this package is
kept for compatibility and comparison.

Pipeline:

```text
用户请求
-> DiagramSpec compiler
-> validator / normalizer
-> template renderer
-> PNG export
```

Key constraints:

- 模板只能表达通用布局族，不能承载具体主题案例。
- LLM output is a `DiagramSpec` only; it must not contain coordinates, SVG, CSS,
  or canvas instructions.
- Fuzzy input returns `needs_clarification` and is blocked before rendering.
- The public figure asset remains PNG-first; the temporary SVG used for export is
  deleted after PNG generation, so `svg_url` stays empty for this route.

Implemented templates:

- `horizontal_stage_cards`
- `snake_cards`
- `grouped_infographic`
- `vertical_layers`
- `shared_resource_three_column`
- `comparison_matrix`
- `comparison_matrix_multi`
- `decision_cards`
- `decision_branch_tree`
- `horizontal_timeline`
- `taxonomy_tree`
- `hub_spoke_concept`
- `mechanism_mapping`
- `mechanism_sequence`
- `parallel_stack_architecture`

Primary entry points:

- `compile_diagram_spec()`
- `validate_and_normalize()`
- `render_infographic_spec()`
