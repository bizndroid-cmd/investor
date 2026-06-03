import { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { PortfolioPage } from "@/pages/PortfolioPage";
import { OrdersPage } from "@/pages/OrdersPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { BrokersPage } from "@/pages/BrokersPage";
import { ComparisonPage } from "@/pages/ComparisonPage";
import { NewsPage } from "@/pages/NewsPage";
import { NerdStatsPage } from "@/pages/NerdStatsPage";
import { LoginPage } from "@/pages/LoginPage";
import { ToastContainer } from "@/components/common/Toast";
import { AlertNotification } from "@/components/alerts/AlertNotification";

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => !!localStorage.getItem("access_token")
  );

  if (!isAuthenticated) {
    return (
      <>
        <LoginPage onLogin={() => setIsAuthenticated(true)} />
        <ToastContainer />
      </>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<DashboardLayout />}>
          <Route path="/" element={<PortfolioPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/brokers" element={<BrokersPage />} />
          <Route path="/comparison" element={<ComparisonPage />} />
          <Route path="/news" element={<NewsPage />} />
          <Route path="/nerd-stats" element={<NerdStatsPage />} />
        </Route>
      </Routes>
      <ToastContainer />
      <AlertNotification />
    </BrowserRouter>
  );
}

export default App;
