import { Download, Loader2, RefreshCw, Sparkles, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import toast from "react-hot-toast";

import {
  EXPORT_EXT,
  exportBook,
  fetchExportPreview,
  refreshExportPreview,
  type ExportFormat,
  type ExportPreview,
  type PageFormatOption,
  type PublicationInfo,
} from "@/api/books";
import CoverLayoutEditor, { type CoverLayout } from "@/components/editor/CoverLayoutEditor";
import { paginateExportPreview } from "@/lib/paginateExportPreview";

const PUB_FIELDS: { key: keyof PublicationInfo; label: string; placeholder?: string; multiline?: boolean }[] = [
  { key: "title", label: "书名", placeholder: "正式书名" },
  { key: "subtitle", label: "副标题", placeholder: "可选" },
  { key: "author", label: "作者", placeholder: "著者姓名" },
  { key: "publisher", label: "出版社", placeholder: "如：某某出版社" },
  { key: "publish_year", label: "出版年", placeholder: "如：2026" },
  { key: "edition", label: "版次", placeholder: "如：第1版" },
  { key: "series", label: "丛书名", placeholder: "可选" },
  { key: "isbn", label: "ISBN", placeholder: "可选" },
  { key: "editor", label: "责任编辑", placeholder: "可选" },
  { key: "proofreader", label: "责任校对", placeholder: "可选" },
  { key: "address", label: "地址", placeholder: "出版社地址" },
  { key: "postal_code", label: "邮编", placeholder: "可选" },
  { key: "price", label: "定价", placeholder: "如：68.00元" },
  { key: "print_count", label: "印数", placeholder: "可选" },
  { key: "word_count_label", label: "字数", placeholder: "如：250千字" },
  { key: "cip_text", label: "CIP 数据", placeholder: "图书在版编目数据", multiline: true },
];

const DEFAULT_LAYOUT: CoverLayout = {
  series: { x: 50, y: 8 },
  title: { x: 50, y: 32 },
  subtitle: { x: 50, y: 44 },
  author: { x: 50, y: 62 },
  publisher: { x: 50, y: 88 },
};

const FALLBACK_FORMATS: PageFormatOption[] = [
  {
    id: "da32_dade",
    label: "大度大 32 开",
    short_label: "大 32 开",
    width_mm: 145,
    height_mm: 210,
    type_area_width_mm: 115,
    type_area_height_mm: 175,
    body_pt: 10.5,
    group: "common",
    hint: "小说、散文、畅销书首选；成品与 A5 一致",
    aka: "A5",
    size_text: "145×210mm",
  },
];

type Props = {
  open: boolean;
  bookId: string;
  bookTitle: string;
  format: ExportFormat;
  onClose: () => void;
};

function emptyPub(title: string): PublicationInfo {
  return {
    title: title || "未命名",
    subtitle: "",
    author: "",
    publisher: "",
    publish_year: "",
    isbn: "",
    edition: "",
    series: "",
    cip_text: "",
    price: "",
    editor: "",
    proofreader: "",
    address: "",
    postal_code: "",
    print_count: "",
    word_count_label: "",
    format_label: "大 32 开",
    page_format_id: "da32_dade",
    binding_type: "paperback",
    cover_layout: { ...DEFAULT_LAYOUT },
    cover_theme: "",
    cover_bg_seed: "",
  };
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ExportPreviewDialog({ open, bookId, bookTitle, format, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [pub, setPub] = useState<PublicationInfo>(() => emptyPub(bookTitle));
  const [layout, setLayout] = useState<CoverLayout>(DEFAULT_LAYOUT);
  const [coverUrl, setCoverUrl] = useState("");
  const [formatOptions, setFormatOptions] = useState<PageFormatOption[]>(FALLBACK_FORMATS);
  const [formatId, setFormatId] = useState("da32_dade");
  const [bindingType, setBindingType] = useState<"paperback" | "hardcover">("paperback");
  const previewRef = useRef<HTMLDivElement>(null);

  const selectedFormat = formatOptions.find((f) => f.id === formatId) || formatOptions[0] || FALLBACK_FORMATS[0];

  const loadPreview = useCallback(
    async (
      info?: PublicationInfo,
      opts?: { persist?: boolean; regenerate_cover_bg?: boolean; quiet?: boolean },
    ): Promise<boolean> => {
      setLoading(true);
      try {
        const payload = info
          ? {
              publication_info: {
                ...info,
                cover_layout: info.cover_layout || layout,
                page_format_id: info.page_format_id || formatId,
                binding_type: info.binding_type || bindingType,
              },
              persist: opts?.persist ?? false,
              regenerate_cover_bg: opts?.regenerate_cover_bg ?? false,
            }
          : undefined;
        const data = payload
          ? await refreshExportPreview(bookId, payload)
          : await fetchExportPreview(bookId);
        setPreview(data);
        const nextPub = { ...emptyPub(bookTitle), ...data.publication_info };
        setPub(nextPub);
        const lay = (data.publication_info.cover_layout as CoverLayout) || DEFAULT_LAYOUT;
        setLayout({ ...DEFAULT_LAYOUT, ...lay });
        setCoverUrl(data.cover_image_data_url || "");
        if (data.page_format_options?.length) setFormatOptions(data.page_format_options);
        const nextFmt = data.page_format?.id || data.publication_info.page_format_id || "da32_dade";
        setFormatId(nextFmt);
        const bt = (data.publication_info.binding_type || data.page_format?.binding_type || "paperback") as
          | "paperback"
          | "hardcover";
        setBindingType(bt === "hardcover" ? "hardcover" : "paperback");
        return true;
      } catch (e) {
        if (!opts?.quiet) toast.error(e instanceof Error ? e.message : "加载预览失败");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [bookId, bookTitle, layout, formatId, bindingType],
  );

  useEffect(() => {
    if (!open) return;
    void loadPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only reload when dialog opens
  }, [open, bookId]);

  useEffect(() => {
    if (!open || !preview?.preview_html || !previewRef.current) return;
    const el = previewRef.current;
    el.innerHTML = preview.preview_html;
    let cancelled = false;
    const w = preview.page_format?.width_mm ?? selectedFormat?.width_mm ?? 145;
    const h = preview.page_format?.height_mm ?? selectedFormat?.height_mm ?? 210;

    const run = () => {
      if (cancelled) return;
      const root = el.querySelector(".export-preview-root") as HTMLElement | null;
      if (!root) return;
      // 等预览区有实际宽度再切页，否则 clientHeight=0 会一页一块
      if (root.clientWidth < 40) {
        window.setTimeout(run, 50);
        return;
      }
      paginateExportPreview(root, { widthMm: w, heightMm: h });
    };

    const id1 = window.requestAnimationFrame(() => {
      window.requestAnimationFrame(run);
    });
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(id1);
    };
  }, [open, preview?.preview_html, preview?.page_format, selectedFormat?.width_mm, selectedFormat?.height_mm]);

  if (!open || typeof document === "undefined") return null;

  const formatLabel =
    format === "docx" ? "Word (.docx)" : format === "pdf" ? "PDF (.pdf)" : "Markdown (.md)";

  function mergedPub(): PublicationInfo {
    return {
      ...pub,
      cover_layout: layout,
      page_format_id: formatId,
      binding_type: bindingType,
      format_label: selectedFormat?.short_label || pub.format_label || "大 32 开",
    };
  }

  async function handleRefresh() {
    await loadPreview(mergedPub(), { persist: false });
  }

  async function handleRegenCover() {
    const toastId = toast.loading("正在用 AI 生成封面背景…");
    const ok = await loadPreview(mergedPub(), { persist: false, regenerate_cover_bg: true, quiet: true });
    if (ok) toast.success("封面背景已更新", { id: toastId });
    else toast.error("封面生成失败，请确认智灵网关已配置", { id: toastId });
  }

  async function handleExport() {
    setExporting(true);
    const toastId = toast.loading("正在导出到本地…");
    try {
      await refreshExportPreview(bookId, {
        publication_info: mergedPub(),
        persist: true,
      });
      const blob = await exportBook(bookId, format);
      const safe =
        (pub.title || bookTitle)
          .replace(/[<>:"/\\|?*\x00-\x1f]/g, "_")
          .trim()
          .slice(0, 80) || "book";
      downloadBlob(blob, `${safe}.${EXPORT_EXT[format]}`);
      toast.success("已导出到本地", { id: toastId });
      onClose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "导出失败", { id: toastId });
    } finally {
      setExporting(false);
    }
  }

  function setField(key: keyof PublicationInfo, value: string) {
    setPub((prev) => ({ ...prev, [key]: value }));
  }

  return createPortal(
    <div className="fixed inset-0 z-[400] flex items-center justify-center bg-slate-900/55 px-3 py-4 sm:px-6">
      <div className="absolute inset-0" aria-hidden onClick={() => !exporting && onClose()} />
      <div className="relative z-[401] flex h-[min(92vh,920px)] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div>
            <h3 className="text-lg font-medium text-ink">导出预览 · {formatLabel}</h3>
            <p className="mt-1 text-xs text-slate-500">
              按所选开本一页一页预览（长章节自动分页）。页码从正文第 1 页起。
            </p>
          </div>
          <button
            type="button"
            className="icon-button h-9 w-9 shrink-0"
            onClick={onClose}
            disabled={exporting}
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
          <aside className="w-full shrink-0 overflow-y-auto border-b border-slate-200 bg-slate-50/80 p-4 lg:w-80 lg:border-b-0 lg:border-r">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">开本选择</p>
            <label className="block text-xs text-slate-600">
              <span className="mb-1 block font-medium text-slate-700">成品尺寸</span>
              <select
                className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm text-ink outline-none focus:border-slate-400"
                value={formatId}
                disabled={loading || exporting}
                onChange={(e) => {
                  const id = e.target.value;
                  setFormatId(id);
                  const opt = formatOptions.find((f) => f.id === id);
                  const nextPub: PublicationInfo = {
                    ...pub,
                    page_format_id: id,
                    binding_type: bindingType,
                    format_label: opt?.short_label || pub.format_label,
                    cover_layout: layout,
                  };
                  setPub(nextPub);
                  void loadPreview(nextPub, { persist: false });
                }}
              >
                <optgroup label="常用开本（约 90% 普通图书）">
                  {formatOptions
                    .filter((f) => f.group === "common")
                    .map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.label} · {f.size_text}
                        {f.aka ? `（${f.aka}）` : ""}
                      </option>
                    ))}
                </optgroup>
                <optgroup label="其他常见开本">
                  {formatOptions
                    .filter((f) => f.group !== "common")
                    .map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.label} · {f.size_text}
                        {f.aka ? `（${f.aka}）` : ""}
                      </option>
                    ))}
                </optgroup>
              </select>
            </label>
            <label className="mt-3 block text-xs text-slate-600">
              <span className="mb-1 block font-medium text-slate-700">装订</span>
              <select
                className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm text-ink outline-none focus:border-slate-400"
                value={bindingType}
                disabled={loading || exporting}
                onChange={(e) => {
                  const bt = e.target.value === "hardcover" ? "hardcover" : "paperback";
                  setBindingType(bt);
                  const nextPub: PublicationInfo = {
                    ...pub,
                    page_format_id: formatId,
                    binding_type: bt,
                    cover_layout: layout,
                  };
                  setPub(nextPub);
                  void loadPreview(nextPub, { persist: false });
                }}
              >
                <option value="paperback">平装（默认）</option>
                <option value="hardcover">精装（订口/天头加宽）</option>
              </select>
            </label>
            {selectedFormat ? (
              <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
                {selectedFormat.hint}
                <br />
                页边距 {selectedFormat.margins_text || "—"}
                <br />
                版心约 {selectedFormat.type_area_width_mm}×{selectedFormat.type_area_height_mm}mm · Word 镜像页边距
              </p>
            ) : null}

            <p className="mb-2 mt-5 text-xs font-medium uppercase tracking-wide text-slate-500">封面排版</p>
            <CoverLayoutEditor
              coverImageUrl={coverUrl}
              layout={layout}
              onChange={setLayout}
              disabled={loading || exporting}
              aspectWidth={selectedFormat?.width_mm ?? 145}
              aspectHeight={selectedFormat?.height_mm ?? 210}
            />
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                className="btn-secondary inline-flex flex-1 items-center justify-center gap-1 text-xs"
                disabled={loading || exporting}
                onClick={() => void handleRegenCover()}
              >
                <Sparkles className="h-3.5 w-3.5" />
                AI 生成封面
              </button>
            </div>
            <p className="mt-1.5 text-[11px] leading-snug text-slate-400">
              调用智灵网关 gpt-image-2 生成封面背景，书名等文字仍可拖拽排版
            </p>

            <p className="mb-2 mt-5 text-xs font-medium uppercase tracking-wide text-slate-500">出版 / 版权信息</p>
            <div className="space-y-2.5">
              {PUB_FIELDS.map((f) => (
                <label key={f.key} className="block text-xs text-slate-600">
                  <span className="mb-1 block font-medium text-slate-700">{f.label}</span>
                  {f.multiline ? (
                    <textarea
                      className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm text-ink outline-none focus:border-slate-400"
                      rows={3}
                      value={(pub[f.key] as string) ?? ""}
                      placeholder={f.placeholder}
                      onChange={(e) => setField(f.key, e.target.value)}
                    />
                  ) : (
                    <input
                      className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm text-ink outline-none focus:border-slate-400"
                      value={(pub[f.key] as string) ?? ""}
                      placeholder={f.placeholder}
                      onChange={(e) => setField(f.key, e.target.value)}
                    />
                  )}
                </label>
              ))}
            </div>
            <button
              type="button"
              className="btn-secondary mt-4 inline-flex w-full items-center justify-center gap-1.5 text-xs"
              disabled={loading || exporting}
              onClick={() => void handleRefresh()}
            >
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              刷新预览
            </button>
          </aside>

          <div className="relative min-h-0 flex-1 overflow-y-auto bg-[#ebe6dc] p-3 sm:p-5">
            {loading && !preview ? (
              <div className="flex h-40 items-center justify-center text-sm text-slate-500">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                生成预览中…
              </div>
            ) : (
              <div
                ref={previewRef}
                className="mx-auto outline-none"
                contentEditable={false}
                suppressContentEditableWarning
                spellCheck={false}
                data-export-preview
              />
            )}
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-slate-200 px-5 py-3">
          <p className="text-[11px] text-slate-400">
            {selectedFormat
              ? `${selectedFormat.label} ${selectedFormat.size_text} · 版心约 ${selectedFormat.type_area_width_mm}×${selectedFormat.type_area_height_mm}mm`
              : "开本可选"}{" "}
            · 封面可拖拽 · 版权页下部排版
          </p>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={exporting}>
              取消
            </button>
            <button
              type="button"
              className="btn-primary inline-flex items-center gap-1.5"
              disabled={exporting || loading}
              onClick={() => void handleExport()}
            >
              {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              导出到本地
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
