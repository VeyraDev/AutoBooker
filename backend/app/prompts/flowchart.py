FLOWCHART_PROMPT = """
将以下流程描述转换为Graphviz DOT代码。
要求：
- 使用 digraph，rankdir=LR（横向）或TB（纵向，默认）
- 节点用圆角矩形（shape=box, style=rounded）
- 判断分支用菱形（shape=diamond）
- 节点/边标签必须使用中文（不要用英文占位）；Graphviz 会自动配置中文字体
- 配色：节点填充#EBF5FB，边框#2E86C1，字体#1C2833
- 只返回DOT代码，不要解释

描述：{description}
""".strip()
