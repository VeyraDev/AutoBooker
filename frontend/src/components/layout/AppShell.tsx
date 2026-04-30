import { Outlet, useLocation } from "react-router-dom";

import AppShellHeader from "@/components/layout/AppShellHeader";

export default function AppShell() {
  const location = useLocation();

  return (
    <div className="app-shell-page">
      <AppShellHeader />
      <main className="app-shell-main">
        <div key={location.pathname} className="page-transition-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
