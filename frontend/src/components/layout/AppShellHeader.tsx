import { Bell, Coins, LogOut, Menu, MessageSquarePlus, Moon, Plus, Sparkles, Sun, UserRound, X } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import FeedbackDialog from "@/components/common/FeedbackDialog";
import NewBookDialog from "@/components/common/NewBookDialog";
import { listNotifications, markNotificationRead } from "@/api/notifications";
import { useAuthStore } from "@/stores/authStore";

const navItems: Array<{ to: string; label: string; badge?: string }> = [
  { to: "/app/home", label: "主页" },
  { to: "/app/books", label: "我的书稿" },
];

export default function AppShellHeader() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const [newBookOpen, setNewBookOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();

  const { data: noticeData } = useQuery({
    queryKey: ["notifications"],
    queryFn: listNotifications,
    refetchInterval: 60000,
  });
  const [theme, setTheme] = useState<"frost" | "warm" | "dark">(() => {
    if (typeof window === "undefined") return "frost";
    return (window.localStorage.getItem("autoBookerTheme") as "frost" | "warm" | "dark") ?? "frost";
  });

  useEffect(() => {
    document.body.classList.remove("theme-frost", "theme-warm", "theme-dark");
    document.body.classList.add(`theme-${theme}`);
    window.localStorage.setItem("autoBookerTheme", theme);
  }, [theme]);

  useEffect(() => {
    function onScroll() {
      setIsScrolled(window.scrollY > 8);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!userMenuOpen) return;
    function onDoc(e: MouseEvent) {
      const target = e.target as Element | null;
      if (target instanceof Element && target.closest(".model-selector-menu")) return;
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [userMenuOpen]);

  function onLogout() {
    logout();
    navigate("/", { replace: true });
    setUserMenuOpen(false);
  }

  return (
    <>
      <header className={`app-header ${isScrolled ? "app-header-scrolled" : ""}`}>
        <div className="mx-auto flex w-full max-w-[92rem] items-center justify-between gap-5 px-6 py-4 sm:px-8">
          <div className="flex shrink-0 items-center gap-2">
            <NavLink to="/app/home" className="shrink-0" aria-label="前往主页">
              <span className="app-brand-mark shrink-0">A</span>
            </NavLink>
            <div className="flex min-w-0 flex-col gap-0.5">
              <NavLink to="/app/home" aria-label="前往主页">
                <span className="app-brand-title">AutoBook</span>
              </NavLink>
              <span className="app-brand-feedback">
                意见反馈：
                <a href="mailto:13523099777@163.com" className="hover:text-brand">
                  13523099777@163.com
                </a>
              </span>
            </div>
          </div>

          <nav className="hidden min-w-0 flex-1 items-center justify-center gap-2 md:flex lg:gap-3" aria-label="主导航">
            {navItems.map((item) => {
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) => `icon-nav ${isActive ? "icon-nav-active" : ""}`}
                  aria-label={item.label}
                  title={item.label}
                >
                  <span className="text-sm font-medium">{item.label}</span>
                  {"badge" in item && item.badge ? (
                    <span className="ml-1 rounded bg-amber-100 px-1 py-0.5 text-[9px] font-medium text-amber-800">
                      {item.badge}
                    </span>
                  ) : null}
                </NavLink>
              );
            })}
          </nav>

          <div className="flex shrink-0 items-center gap-3 sm:gap-5">
            <button
              type="button"
              className="btn-primary hidden h-10 px-4 text-sm sm:inline-flex"
              onClick={() => setNewBookOpen(true)}
              aria-label="新建书稿"
            >
              <Plus className="mr-1 h-4 w-4" />
              新建书稿
            </button>
            <div className="balance-card hidden lg:inline-flex" aria-label="账户余额">
              <Coins className="h-4 w-4 text-amber-400" />
              <span>98</span>
            </div>
            <button
              type="button"
              className="icon-button hidden sm:inline-flex"
              aria-label="意见反馈"
              title="意见反馈"
              onClick={() => setFeedbackOpen(true)}
            >
              <MessageSquarePlus className="h-4.5 w-4.5" />
            </button>
            <div className="relative hidden sm:block">
              <button
                type="button"
                className="icon-button icon-button-notice"
                aria-label="消息通知"
                title="消息通知"
                onClick={() => setNoticeOpen((v) => !v)}
              >
                <Bell className="h-4.5 w-4.5" />
                {(noticeData?.unread_count ?? 0) > 0 ? (
                  <span className="icon-badge" aria-hidden>
                    {noticeData!.unread_count > 9 ? "9+" : noticeData!.unread_count}
                  </span>
                ) : null}
              </button>
              {noticeOpen ? (
                <div className="absolute right-0 top-[calc(100%+8px)] z-50 w-80 rounded-xl border border-slate-200 bg-white py-2 shadow-xl">
                  <p className="border-b border-slate-100 px-3 pb-2 text-xs font-medium text-slate-500">通知</p>
                  <ul className="max-h-64 overflow-y-auto">
                    {(noticeData?.items ?? []).slice(0, 20).map((n) => (
                      <li key={n.id}>
                        <button
                          type="button"
                          className={`w-full px-3 py-2 text-left text-xs hover:bg-slate-50 ${n.is_read ? "text-slate-500" : "text-ink font-medium"}`}
                          onClick={() => {
                            void markNotificationRead(n.id).then(() => qc.invalidateQueries({ queryKey: ["notifications"] }));
                            const bid = n.payload_json?.book_id;
                            if (typeof bid === "string") navigate(`/app/books/${bid}`);
                            setNoticeOpen(false);
                          }}
                        >
                          <p>{n.title}</p>
                          {n.body ? <p className="mt-0.5 text-[10px] text-slate-400 line-clamp-2">{n.body}</p> : null}
                        </button>
                      </li>
                    ))}
                    {!noticeData?.items?.length ? (
                      <li className="px-3 py-4 text-center text-xs text-slate-400">暂无通知</li>
                    ) : null}
                  </ul>
                </div>
              ) : null}
            </div>

            <div className="flex flex-col items-center gap-0.5">
              <div className="relative" ref={userMenuRef}>
                <button
                  type="button"
                  className={`icon-button ${userMenuOpen ? "ring-2 ring-brand/30" : ""}`}
                  aria-expanded={userMenuOpen}
                  aria-haspopup="menu"
                  aria-label="账户菜单"
                  title={user?.email ?? "账户"}
                  onClick={() => setUserMenuOpen((v) => !v)}
                >
                  <UserRound className="h-4.5 w-4.5" />
                </button>
                {userMenuOpen ? (
                <div
                  role="menu"
                  className="absolute right-0 top-[calc(100%+8px)] z-50 w-80 rounded-xl border border-slate-200 bg-white py-3 shadow-xl"
                >
                  <p className="border-b border-slate-100 px-3 pb-2 text-xs text-slate-500">{user?.email ?? "用户"}</p>
                  <p className="px-3 pb-2 pt-2 text-[11px] font-medium uppercase tracking-wide text-slate-400">主题</p>
                  <div className="flex gap-2 px-3 pb-3">
                    <button
                      type="button"
                      title="雾光"
                      className={`flex h-10 flex-1 items-center justify-center rounded-lg border ${theme === "frost" ? "border-brand bg-brand/10" : "border-slate-200"}`}
                      onClick={() => setTheme("frost")}
                    >
                      <Sparkles className="h-4 w-4 text-slate-700" />
                    </button>
                    <button
                      type="button"
                      title="暖杏"
                      className={`flex h-10 flex-1 items-center justify-center rounded-lg border ${theme === "warm" ? "border-brand bg-brand/10" : "border-slate-200"}`}
                      onClick={() => setTheme("warm")}
                    >
                      <Sun className="h-4 w-4 text-amber-600" />
                    </button>
                    <button
                      type="button"
                      title="暗夜"
                      className={`flex h-10 flex-1 items-center justify-center rounded-lg border ${theme === "dark" ? "border-brand bg-brand/10" : "border-slate-200"}`}
                      onClick={() => setTheme("dark")}
                    >
                      <Moon className="h-4 w-4 text-slate-700" />
                    </button>
                  </div>
                  <button
                    type="button"
                    role="menuitem"
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                    onClick={onLogout}
                  >
                    <LogOut className="h-4 w-4 shrink-0" />
                    退出登录
                  </button>
                </div>
                ) : null}
              </div>
            </div>

            <button
              type="button"
              className="icon-button md:hidden"
              onClick={() => setMobileMenuOpen((v) => !v)}
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-app-nav"
              aria-label={mobileMenuOpen ? "关闭导航菜单" : "打开导航菜单"}
              title={mobileMenuOpen ? "关闭菜单" : "菜单"}
            >
              {mobileMenuOpen ? <X className="h-4.5 w-4.5" /> : <Menu className="h-4.5 w-4.5" />}
            </button>
          </div>
        </div>
        {mobileMenuOpen && (
          <nav id="mobile-app-nav" className="border-t border-slate-200/70 bg-white px-4 py-4 md:hidden" aria-label="移动端主导航">
            <button type="button" className="btn-primary mb-3 w-full sm:hidden" onClick={() => { setNewBookOpen(true); setMobileMenuOpen(false); }}>
              <Plus className="mr-1 inline h-4 w-4" />
              新建书稿
            </button>
            <div className="grid grid-cols-2 gap-2">
              {navItems.map((item) => {
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={() => setMobileMenuOpen(false)}
                    className={({ isActive }) => `icon-nav justify-center ${isActive ? "icon-nav-active" : ""}`}
                  >
                    <span className="text-xs">{item.label}</span>
                    {"badge" in item && item.badge ? (
                      <span className="ml-1 rounded bg-amber-100 px-1 py-0.5 text-[9px] text-amber-800">{item.badge}</span>
                    ) : null}
                  </NavLink>
                );
              })}
            </div>
            <button type="button" onClick={() => { onLogout(); setMobileMenuOpen(false); }} className="btn-secondary mt-3 w-full">
              退出登录
            </button>
          </nav>
        )}
      </header>
      <NewBookDialog open={newBookOpen} onClose={() => setNewBookOpen(false)} />
      <FeedbackDialog open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </>
  );
}
