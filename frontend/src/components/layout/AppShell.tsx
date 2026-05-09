import { Outlet, useLocation, useMatch } from "react-router-dom";

import AppShellHeader from "@/components/layout/AppShellHeader";

export default function AppShell() {
  const location = useLocation();
  /** 书稿编辑页使用自带顶栏，不显示主系统导航 */
  const hideAppChrome = Boolean(useMatch("/app/books/:bookId"));

  return (
    <div className={`app-shell-page${hideAppChrome ? " app-shell-page--editor" : ""}`}>
      {!hideAppChrome && <AppShellHeader />}
      <main className={`app-shell-main${hideAppChrome ? " app-shell-main--editor" : ""}`}>
        <div
          key={location.pathname}
          className={`page-transition-in${hideAppChrome ? " page-transition-in--editor" : ""}`}
        >
          <Outlet />
        </div>
      </main>
    </div>
  );
}
