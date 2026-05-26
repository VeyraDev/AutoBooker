CHART_PARSE_PROMPT = """
将以下图表描述解析为JSON，只返回JSON：
{{
  "chart_type": "line|bar|scatter|heatmap|pie",
  "title": "图表标题",
  "x_label": "X轴标签",
  "y_label": "Y轴标签",
  "series": [
    {{
      "name": "系列名",
      "data": [[x1,y1], [x2,y2]]
    }}
  ],
  "annotations": ["在x=20处标注'过拟合拐点'"]
}}
如果描述中没有具体数字，根据描述生成合理的示意数据，
并在JSON中加 "is_illustrative": true 标记。

描述：{description}
""".strip()
