import { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { PortfolioPage } from "@/pages/PortfolioPage";
import { OrdersPage } from "@/pages/OrdersPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { BrokersPage } from "@/pages/BrokersPage";
import { ComparisonPage } from "@/pages/ComparisonPage";
import { DetailedNewsPage } from "@/pages/DetailedNewsPage";
import { ETFsPage } from "@/pages/ETFsPage";
import { GoalsPage } from "@/pages/GoalsPage";
import { ImportsPage } from "@/pages/ImportsPage";
import { EarningsPage } from "@/pages/EarningsPage";
import { AttachmentsPage } from "@/pages/AttachmentsPage";
import { PredictionsPage } from "@/pages/PredictionsPage";
import { InsightsPage } from "@/pages/InsightsPage";
import { ResearchPage } from "@/pages/ResearchPage";
import { NerdStatsPage } from "@/pages/NerdStatsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { DailyBriefingPage } from "@/pages/DailyBriefingPage";
import { LoginPage } from "@/pages/LoginPage";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { ToastContainer } from "@/components/common/Toast";
import { AlertNotification } from "@/components/alerts/AlertNotification";

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => !!localStorage.getItem("access_token")
  );
  const [showOnboarding, setShowOnboarding] = useState(false);

  if (!isAuthenticated) {
    if (showOnboarding) {
      return (
        <>
          <OnboardingPage onComplete={() => setIsAuthenticated(true)} />
          <ToastContainer />
        </>
      );
    }

    return (
      <>
        <LoginPage
          onLogin={() => setIsAuthenticated(true)}
          onRegister={() => setShowOnboarding(true)}
        />
        <ToastContainer />
      </>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<DashboardLayout />}>
          {/* Primary pages (in sidebar) */}
          <Route path="/" element={<PortfolioPage />} />
          <Route path="/earnings" element={<EarningsPage />} />
          <Route path="/etfs" element={<ETFsPage />} />
          <Route path="/goals" element={<GoalsPage />} />
          <Route path="/research" element={<ResearchPage />} />
          <Route path="/briefing" element={<DailyBriefingPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/brokers" element={<BrokersPage />} />
          <Route path="/imports" element={<ImportsPage />} />
          <Route path="/settings" element={<SettingsPage />} />

          {/* Hidden pages (accessible via URL, not in sidebar) */}
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/comparison" element={<ComparisonPage />} />
          <Route path="/attachments" element={<AttachmentsPage />} />
          <Route path="/nerd-stats" element={<NerdStatsPage />} />
          <Route path="/insights" element={<InsightsPage />} />
          <Route path="/predictions" element={<PredictionsPage />} />
          <Route path="/news" element={<DetailedNewsPage />} />
        </Route>
      </Routes>
      <ToastContainer />
      <AlertNotification />
    </BrowserRouter>
  );
}

export default App;
