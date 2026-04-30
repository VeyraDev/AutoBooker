import { Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "@/components/common/ProtectedRoute";
import AppShell from "@/components/layout/AppShell";
import BookEditorPage from "@/pages/BookEditorPage";
import BooksPage from "@/pages/BooksPage";
import HomePage from "@/pages/HomePage";
import LandingPage from "@/pages/LandingPage";
import LoginPage from "@/pages/LoginPage";
import ProfilePage from "@/pages/ProfilePage";
import RegisterPage from "@/pages/RegisterPage";
import StatsPage from "@/pages/StatsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Navigate to="/app/home" replace />} />
          <Route path="home" element={<HomePage />} />
          <Route path="books" element={<BooksPage />} />
          <Route path="books/:bookId" element={<BookEditorPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="stats" element={<StatsPage />} />
        </Route>
      </Route>
      <Route path="/dashboard" element={<Navigate to="/app/home" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
