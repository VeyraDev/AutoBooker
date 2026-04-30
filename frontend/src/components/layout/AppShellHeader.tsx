import {
  Bell,
  Coins,
  LogOut,
  Menu,
  X,
  UserRound,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";

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

  useEffect(() => {
    function onScroll() {
      setIsScrolled(window.scrollY > 8);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function onLogout() {
    logout();
    navigate("/", { replace: true });
  }

  return (
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

        <div className="flex shrink-0 items-center gap-2.5">
          <button type="button" className="balance-pill hidden lg:inline-flex" aria-label="账户余额" title="账户余额">
            <Coins className="h-4.5 w-4.5" />
            <span>98</span>
          </button>
          <button type="button" className="icon-button icon-button-notice" aria-label="消息通知" title="消息通知">
            <Bell className="h-4.5 w-4.5" />
            <span className="icon-badge" aria-hidden>
              3
            </span>
          </button>
          <button type="button" className="icon-button" aria-label="个人账户" title={user?.email ?? "账户"}>
            <UserRound className="h-4.5 w-4.5" />
          </button>
          <button type="button" onClick={onLogout} className="icon-button hidden sm:inline-flex" aria-label="退出登录" title="退出登录">
            <LogOut className="h-4.5 w-4.5" />
          </button>
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
        <nav id="mobile-app-nav" className="border-t border-slate-200/70 bg-white/92 px-4 py-4 backdrop-blur md:hidden" aria-label="移动端主导航">
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
          <button type="button" onClick={onLogout} className="btn-secondary mt-3 w-full">
            退出登录
          </button>
        </nav>
      )}
    </header>
  );
}
