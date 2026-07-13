import { Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "@/components/common/ProtectedRoute";
import AppShell from "@/components/layout/AppShell";
import AutoBookProgressPage from "@/pages/AutoBookProgressPage";
import BookEditorPage from "@/pages/BookEditorPage";
import BooksPage from "@/pages/BooksPage";
import HomePage from "@/pages/HomePage";
import LandingPage from "@/pages/LandingPage";
import LibraryPage from "@/pages/LibraryPage";
import LoginPage from "@/pages/LoginPage";
import OptimizationPage from "@/pages/OptimizationPage";
import ReviewWorkspacePage from "@/features/review/ReviewWorkspacePage";
import RegisterPage from "@/pages/RegisterPage";

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
          <Route path="library" element={<LibraryPage />} />
          <Route path="books/:bookId/auto-progress" element={<AutoBookProgressPage />} />
          <Route path="books/:bookId/optimize" element={<OptimizationPage />} />
          <Route path="books/:bookId/review" element={<ReviewWorkspacePage />} />
          <Route path="books/:bookId" element={<BookEditorPage />} />
        </Route>
      </Route>
      <Route path="/dashboard" element={<Navigate to="/app/home" replace />} />
      <Route path="/app/profile" element={<Navigate to="/app/home" replace />} />
      <Route path="/app/stats" element={<Navigate to="/app/home" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
