FLOWCHART_PROMPT = """
将以下流程描述转换为 Graphviz DOT 代码。
硬性约束：
- 使用 digraph；流程图 rankdir=LR，层级图 rankdir=TB
- 节点 shape=box, style=rounded；判断分支用 shape=diamond（全图最多 1 个菱形）
- 单节点 label 不超过 20 字，超长用 \\n 换行
- graph [nodesep=0.8, ranksep=1.0, splines=ortho, bgcolor=white]
- 同级节点用 {{ rank=same; nodeA; nodeB; }} 对齐；同一 rank 层最多 4 个节点
- 节点/边标签使用中文；配色：填充 #EBF5FB，边框 #2E86C1，字体 #1C2833
- 只返回 DOT 代码，不要解释

描述：{description}
""".strip()
