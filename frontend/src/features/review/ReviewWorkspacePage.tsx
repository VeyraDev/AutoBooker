import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useMemo, useState } from "react";
import toast from "react-hot-toast";
import { useNavigate, useParams } from "react-router-dom";

import { getBook, updateBook } from "@/api/books";
import { getOutline } from "@/api/outline";
import ReviewFindingDetail from "@/features/review/ReviewFindingDetail";
import ReviewFindingList from "@/features/review/ReviewFindingList";
import ReviewScopeNav from "@/features/review/ReviewScopeNav";
import {
  batchPreviewReviewWorkspaceFindings,
  getReviewWorkspaceSummary,
  listReviewWorkspaceFindings,
  runCustomReview,
  runReviewWorkspace,
  type ProductDimension,
  type WorkspaceFinding,
} from "@/features/review/reviewWorkspaceApi";

export default function ReviewWorkspacePage() {
  const { bookId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null);
  const [selectedTier, setSelectedTier] = useState<string | null>(null);
  const [selectedDimension, setSelectedDimension] = useState<ProductDimension | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<WorkspaceFinding | null>(null);
  const [showObserve, setShowObserve] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");
  const [completing, setCompleting] = useState(false);

  const bookQ = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId!),
    enabled: !!bookId,
  });

  const outlineQ = useQuery({
    queryKey: ["outline", bookId],
    queryFn: () => getOutline(bookId!),
    enabled: !!bookId,
  });

  const summaryQ = useQuery({
    queryKey: ["reviewWorkspaceSummary", bookId],
    queryFn: () => getReviewWorkspaceSummary(bookId!),
    enabled: !!bookId,
  });

  const statusParam = selectedTier === "resolved" || selectedTier === "dismissed" ? selectedTier : selectedTier === "observe" ? undefined : "open";

  const findingsQ = useQuery({
    queryKey: ["reviewWorkspaceFindings", bookId, selectedChapter, selectedTier, selectedDimension],
    queryFn: () =>
      listReviewWorkspaceFindings(bookId!, {
        chapter_index: selectedChapter ?? undefined,
        tier: selectedTier && !["resolved", "dismissed"].includes(selectedTier) ? (selectedTier as "must_fix" | "suggest" | "observe" | "needs_verification") : undefined,
        status: statusParam,
        product_dimension: selectedDimension ?? undefined,
      }),
    enabled: !!bookId,
  });

  const runMut = useMutation({
    mutationFn: (body: { scope: "book" | "chapter"; chapter_index?: number }) => runReviewWorkspace(bookId!, body),
    onSuccess: (data) => {
      toast.success(data.message || "审校完成");
      void qc.invalidateQueries({ queryKey: ["reviewWorkspaceSummary", bookId] });
      void qc.invalidateQueries({ queryKey: ["reviewWorkspaceFindings", bookId] });
    },
    onError: () => toast.error("审校失败"),
  });

  const customMut = useMutation({
    mutationFn: () =>
      runCustomReview(bookId!, {
        prompt: customPrompt.trim(),
        chapter_index: selectedChapter ?? undefined,
      }),
    onSuccess: (data) => {
      toast.success(data.message || "专项审校完成");
      void qc.invalidateQueries({ queryKey: ["reviewWorkspaceSummary", bookId] });
      void qc.invalidateQueries({ queryKey: ["reviewWorkspaceFindings", bookId] });
    },
    onError: () => toast.error("专项审校失败"),
  });

  const batchPreviewMut = useMutation({
    mutationFn: (findingIds: string[]) =>
      batchPreviewReviewWorkspaceFindings(bookId!, {
        finding_ids: findingIds,
        limit: 10,
      }),
    onSuccess: (data) => {
      toast.success(`已生成 ${data.previewed_count} 条修改预览，跳过 ${data.skipped_count} 条`);
      void qc.invalidateQueries({ queryKey: ["reviewWorkspaceFindings", bookId] });
    },
    onError: () => toast.error("批量生成预览失败"),
  });

  const chapterIndexes = useMemo(
    () => (outlineQ.data?.chapters ?? []).map((c) => c.index).sort((a, b) => a - b),
    [outlineQ.data?.chapters],
  );

  const visibleFindings = useMemo(() => {
    let rows = findingsQ.data ?? [];
    if (selectedTier === "resolved" || selectedTier === "dismissed") {
      return rows;
    }
    if (!showObserve && !selectedTier) {
      rows = rows.filter((f) => f.tier !== "observe");
    }
    return rows;
  }, [findingsQ.data, showObserve, selectedTier]);

  const batchPreviewableIds = useMemo(
    () =>
      visibleFindings
        .filter(
          (finding) =>
            finding.source === "chapter" &&
            finding.status === "open" &&
            finding.locatable &&
            finding.fix_capability === "preview_apply",
        )
        .map((finding) => finding.id),
    [visibleFindings],
  );

  async function handleCompleteBook() {
    if (!bookId) return;
    setCompleting(true);
    try {
      await updateBook(bookId, { status: "completed" });
      await qc.invalidateQueries({ queryKey: ["book", bookId] });
      toast.success("全书已完成");
    } catch {
      toast.error("完成全书失败");
    } finally {
      setCompleting(false);
    }
  }

  if (!bookId) return <p className="p-8 text-sm text-slate-500">无效路由</p>;
  if (bookQ.isLoading || !bookQ.data) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-sm text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin" /> 加载中…
      </div>
    );
  }

  const book = bookQ.data;
  const summary = summaryQ.data;

  return (
    <div className="flex h-[calc(100vh-3rem)] min-h-0 flex-col bg-white">
      <div className="border-b border-amber-100 bg-amber-50 px-4 py-2 text-xs text-amber-900">
        审校用于发现修改建议，不影响全书完成或导出。
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-[260px_minmax(280px,1fr)_minmax(320px,1.1fr)]">
        <ReviewScopeNav
          chapterIndexes={chapterIndexes}
          selectedChapter={selectedChapter}
          selectedTier={selectedTier}
          selectedDimension={selectedDimension}
          onSelectChapter={(idx) => {
            setSelectedChapter(idx);
            setSelectedFinding(null);
          }}
          onSelectTier={setSelectedTier}
          onSelectDimension={setSelectedDimension}
          mustFixCount={summary?.must_fix_count ?? 0}
          suggestCount={summary?.suggest_count ?? 0}
          observeCount={summary?.observe_count ?? 0}
          needsVerificationCount={summary?.needs_verification_count ?? 0}
          runStatus={summary?.run_status ?? null}
          latestTask={summary?.latest_task ?? null}
          running={runMut.isPending || customMut.isPending}
          customPrompt={customPrompt}
          onCustomPromptChange={setCustomPrompt}
          onRunBook={() => runMut.mutate({ scope: "book" })}
          onRunChapter={() => {
            if (selectedChapter == null) {
              toast.error("请先选择章节");
              return;
            }
            runMut.mutate({ scope: "chapter", chapter_index: selectedChapter });
          }}
          onRunCustom={() => customMut.mutate()}
          onBack={() => navigate(`/app/books/${bookId}`)}
          showCompleteBook={book.status === "review_ready"}
          onCompleteBook={handleCompleteBook}
          completing={completing}
        />
        <ReviewFindingList
          findings={visibleFindings}
          selectedId={selectedFinding?.id ?? null}
          onSelect={setSelectedFinding}
          showObserve={showObserve}
          onToggleObserve={() => setShowObserve((v) => !v)}
          tierFilter={selectedTier}
          batchPreviewableCount={batchPreviewableIds.length}
          batchPreviewBusy={batchPreviewMut.isPending}
          onBatchPreview={() => {
            if (!batchPreviewableIds.length) {
              toast.error("当前筛选下没有可自动生成预览的问题");
              return;
            }
            batchPreviewMut.mutate(batchPreviewableIds);
          }}
        />
        <ReviewFindingDetail
          bookId={bookId}
          finding={selectedFinding}
          onUpdated={() => {
            void qc.invalidateQueries({ queryKey: ["reviewWorkspaceSummary", bookId] });
            void qc.invalidateQueries({ queryKey: ["reviewWorkspaceFindings", bookId] });
          }}
        />
      </div>
    </div>
  );
}
