# Figure Render Pipelines

The render layer keeps the three figure rendering families separate:

- `image_api/`: full Image API route. It owns layout-script prompt planning,
  provider selection, and OpenAI/Wanx PNG generation.
- `compositor/`: default structural PNG route. It enumerates generic layouts
  such as linear, snake, branch, tree, matrix, timeline, radial, grid, and
  layers without embedding domain-specific templates.
- `html_template/`: deterministic template route. It compiles supported
  structural requests into `DiagramSpec`, renders template SVG, and exports PNG.
  This route is retained for compatibility and is not the default structural
  outlet.
- `legacy_svg/`, `structured/`, and `svg/`: legacy/manual structured SVG route.
  `legacy_svg/` owns the old Graphviz/template helpers, `svg/` owns shared SVG
  primitives, and `structured/` contains the active structured renderer adapters.
- `structured/chart_matplotlib.py`: chart route. Data charts stay on the
  Matplotlib path and do not enter Image API or HTML template rendering.

Compatibility wrappers may remain under `app.services.figure_render`, but new
code should import from this package so pipeline ownership stays explicit.
