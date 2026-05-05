import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import axios from "axios";

import { loginApi, meApi } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setTokens, setUser } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password.length < 6) {
      toast.error("密码至少 6 位");
      return;
    }
    setSubmitting(true);
    try {
      const tokens = await loginApi(email, password);
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await meApi();
      setUser(user);
      const from = (location.state as { from?: string } | null)?.from ?? "/app/home";
      navigate(from, { replace: true });
    } catch (err) {
      const msg =
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "登录失败，请重试";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-shell page-transition-in">
      <div className="auth-wrapper auth-wrapper-single">
        <div className="flex flex-col justify-center">
          <h1 className="text-2xl font-medium text-ink mb-1">欢迎回到 AutoBooker</h1>
          <p className="text-sm text-slate-500 mb-6">登录以继续创作你的下一本书</p>
          <form onSubmit={onSubmit} className="auth-form">
            <div>
              <label className="block text-sm text-slate-600 mb-1">邮箱</label>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">密码</label>
              <input
                type="password"
                required
                minLength={6}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="至少 6 位"
              />
            </div>
            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? "登录中..." : "登录"}
            </button>
          </form>
          <p className="text-sm text-slate-500 mt-4 text-center">
            还没有账号？{" "}
            <Link to="/register" className="text-brand hover:underline">
              注册一个
            </Link>
          </p>
          <p className="mt-4 text-center text-xs text-slate-400">
            登录即表示你同意平台的基础使用规范与数据处理方式
          </p>
        </div>
      </div>
    </div>
  );
}
