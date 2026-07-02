import { BookOpen, Construction } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function LibraryPage() {
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6 flex items-center gap-3">
        <BookOpen className="h-7 w-7 text-indigo-600" />
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-ink">系统书库</h1>
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">待开发</span>
          </div>
          <p className="text-sm text-slate-500">经典 AI 文献与社区贡献，可加入书稿引用库</p>
        </div>
      </div>

      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/80 px-6 py-20 text-center">
        <Construction className="mb-4 h-10 w-10 text-slate-400" />
        <p className="text-base font-medium text-ink">系统书库功能开发中</p>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-slate-500">
          经典文献检索、社区贡献与引用库管理即将上线，敬请期待。
        </p>
        <button type="button" className="btn-secondary mt-8 text-sm" onClick={() => navigate("/app/home")}>
          返回主页
        </button>
      </div>
    </div>
  );
}
