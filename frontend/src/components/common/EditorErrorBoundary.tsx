import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };

type State = { error: Error | null };

/**
 * 防止 TipTap / ProseMirror 或子树抛错导致整页白屏；按章节 key 挂载可自动恢复。
 */
export default class EditorErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.warn("[EditorErrorBoundary]", error.message, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="rounded-lg border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">正文编辑器加载异常</p>
          <p className="mt-1 text-xs leading-relaxed opacity-90">
            常见原因：章节保存的文档格式与当前编辑器不兼容。请尝试刷新页面或切换章节；若仍失败，可联系管理员检查该章数据。
          </p>
          <button
            type="button"
            className="mt-3 text-sm font-medium text-violet-700 underline hover:text-violet-900"
            onClick={() => this.setState({ error: null })}
          >
            重试渲染
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
