import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { meApi } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

export default function ProtectedRoute() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const setUser = useAuthStore((s) => s.setUser);
  const location = useLocation();

  useEffect(() => {
    if (!accessToken) return;
    void meApi()
      .then(setUser)
      .catch(() => {
        /* 401 由 client 拦截器处理 */
      });
  }, [accessToken, setUser]);

  if (!accessToken) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
