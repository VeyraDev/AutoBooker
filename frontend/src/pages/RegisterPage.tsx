import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import axios from "axios";

import { meApi, registerApi } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

export default function RegisterPage() {
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password.length < 6) {
      toast.error("密码至少 6 位");
      return;
    }
    if (password !== confirm) {
      toast.error("两次输入的密码不一致");
      return;
    }
    setSubmitting(true);
    try {
      const tokens = await registerApi(email, password);
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await meApi();
      setUser(user);
      navigate("/app/home", { replace: true });
    } catch (err) {
      const msg =
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "注册失败，请重试";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-shell page-transition-in">
      <div className="auth-wrapper">
        <div className="auth-panel">
          <p className="text-sm text-brand-100">AutoBooker</p>
          <h2 className="mt-2 text-2xl font-medium leading-tight">今天开始你的第一本书</h2>
          <p className="mt-4 text-sm text-brand-100/95">
            只需一个邮箱账号，即可建立项目、管理结构并持续输出。
          </p>
          <ul className="mt-6 space-y-3 text-sm text-brand-50">
            <li>· 支持非虚构与学术两类项目</li>
            <li>· 统一看板管理创作流程</li>
            <li>· 随时回到上次创作位置</li>
          </ul>
        </div>
        <div className="flex flex-col justify-center">
          <h1 className="text-2xl font-medium text-ink mb-1">创建 AutoBooker 账号</h1>
          <p className="text-sm text-slate-500 mb-6">用邮箱注册即可开始创作</p>
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
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="至少 6 位"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">确认密码</label>
              <input
                type="password"
                required
                minLength={6}
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="input"
                placeholder="再输一次"
              />
            </div>
            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? "注册中..." : "注册"}
            </button>
          </form>
          <p className="text-sm text-slate-500 mt-4 text-center">
            已有账号？{" "}
            <Link to="/login" className="text-brand hover:underline">
              去登录
            </Link>
          </p>
          <p className="mt-4 text-center text-xs text-slate-400">
            创建账号即表示你同意平台基础条款并授权必要的登录校验
          </p>
        </div>
      </div>
    </div>
  );
}
