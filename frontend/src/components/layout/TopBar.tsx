import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useAuthStore } from "@/stores/authStore";

export default function TopBar() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  function onLogout() {
    logout();
    navigate("/", { replace: true });
  }

  return (
    <header className="sticky top-0 z-10 border-b border-slate-200/70 bg-white/95 px-6 py-3 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="inline-block h-7 w-7 rounded bg-brand" aria-hidden />
          <div>
            <span className="block text-base font-medium tracking-tight text-ink">AutoBooker</span>
            <span className="block text-xs text-slate-400">智能写作看板</span>
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="hidden sm:inline">{user?.email}</span>
          <button
            type="button"
            onClick={onLogout}
            className="inline-flex items-center gap-1 rounded px-2 py-1 hover:bg-slate-100"
          >
            <LogOut className="h-4 w-4" />
            <span>退出</span>
          </button>
        </div>
      </div>
    </header>
  );
}
