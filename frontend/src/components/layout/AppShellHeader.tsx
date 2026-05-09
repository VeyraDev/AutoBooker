import { Bell, Coins, LogOut, Menu, Moon, Plus, Sparkles, Sun, UserRound, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import NewBookDialog from "@/components/common/NewBookDialog";
import { useAuthStore } from "@/stores/authStore";

const navItems = [
  { to: "/app/home", label: "主页" },
  { to: "/app/books", label: "图书管理" },
  { to: "/app/profile", label: "个人主页" },
  { to: "/app/stats", label: "数据统计" },
];

export default function AppShellHeader() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const [newBookOpen, setNewBookOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
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
            <NavLink to="/app/home" className="flex items-center gap-2" aria-label="前往主页">
              <span className="app-brand-mark">A</span>
              <span className="app-brand-title">AutoBooker</span>
            </NavLink>
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
            <button type="button" className="icon-button icon-button-notice hidden sm:inline-flex" aria-label="消息通知" title="消息通知">
              <Bell className="h-4.5 w-4.5" />
              <span className="icon-badge" aria-hidden>
                3
              </span>
            </button>

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
                  className="absolute right-0 top-[calc(100%+8px)] z-50 w-56 rounded-xl border border-slate-200 bg-white py-3 shadow-xl"
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
    </>
  );
}
