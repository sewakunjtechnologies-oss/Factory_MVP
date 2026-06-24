import { lazy, Suspense } from "react";
import { Capacitor } from "@capacitor/core";
import { Navigate, Route, Routes } from "react-router-dom";

import { LoadingState } from "./components/LoadingState";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AppLayout } from "./layouts/AppLayout";
import { MobileLayout } from "./layouts/MobileLayout";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const POListPage = lazy(() => import("./pages/POListPage"));
const CreatePOPage = lazy(() => import("./pages/CreatePOPage"));
const PODetailPage = lazy(() => import("./pages/PODetailPage"));
const FabricPage = lazy(() => import("./pages/FabricPage"));
const FabricOrdersPage = lazy(() => import("./pages/FabricOrdersPage"));
const StageAllocationPage = lazy(() => import("./pages/StageAllocationPage"));
const ProductionPage = lazy(() => import("./pages/ProductionPage"));
const PackingPage = lazy(() => import("./pages/PackingPage"));
const PackingMaterialsPage = lazy(() => import("./pages/PackingMaterialsPage"));
const ContractorsPage = lazy(() => import("./pages/ContractorsPage"));
const DispatchPage = lazy(() => import("./pages/DispatchPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const RemindersPage = lazy(() => import("./pages/RemindersPage"));
const AssistantPage = lazy(() => import("./pages/AssistantPage"));
const FabricLinesPage = lazy(() => import("./pages/FabricLinesPage"));
const AiImportPage = lazy(() => import("./pages/AiImportPage"));
const MobileHomePage = lazy(() => import("./pages/mobile/MobileHomePage"));
const MobilePOListPage = lazy(() => import("./pages/mobile/MobilePOListPage"));
const MobileCreatePOPage = lazy(() => import("./pages/mobile/MobileCreatePOPage"));
const MobilePODetailPage = lazy(() => import("./pages/mobile/MobilePODetailPage"));
const MobileAssistantPage = lazy(() => import("./pages/mobile/MobileAssistantPage"));
const MobileAlertsPage = lazy(() => import("./pages/mobile/MobileAlertsPage"));

function DefaultLanding() {
  return <Navigate to={Capacitor.isNativePlatform() ? "/mobile/home" : "/dashboard"} replace />;
}

export default function App() {
  return (
    <Suspense fallback={<div className="p-6"><LoadingState /></div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<MobileLayout />}>
            <Route path="/mobile" element={<Navigate to="/mobile/home" replace />} />
            <Route path="/mobile/home" element={<MobileHomePage />} />
            <Route path="/mobile/pos" element={<MobilePOListPage />} />
            <Route path="/mobile/po/create" element={<MobileCreatePOPage />} />
            <Route path="/mobile/po/:id" element={<MobilePODetailPage />} />
            <Route path="/mobile/assistant" element={<MobileAssistantPage />} />
            <Route path="/mobile/alerts" element={<MobileAlertsPage />} />
            <Route path="/mobile/reports" element={<MobileAssistantPage />} />
            <Route path="/mobile/settings" element={<MobileHomePage />} />
          </Route>
          <Route element={<AppLayout />}>
            <Route index element={<DefaultLanding />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/pos" element={<POListPage />} />
            <Route path="/pos/create" element={<CreatePOPage />} />
            <Route path="/po/:id" element={<PODetailPage />} />
            <Route path="/inventory" element={<FabricLinesPage />} />
            <Route path="/fabric" element={<FabricPage />} />
            <Route path="/fabric-ops" element={<FabricOrdersPage />} />
            <Route path="/allocation" element={<StageAllocationPage />} />
            <Route path="/production" element={<ProductionPage />} />
            <Route path="/packing" element={<PackingPage />} />
            <Route path="/packing-materials" element={<PackingMaterialsPage />} />
            <Route path="/contractors" element={<ContractorsPage />} />
            <Route path="/dispatch" element={<DispatchPage />} />
            <Route path="/reminders" element={<RemindersPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/assistant" element={<AssistantPage />} />
            <Route path="/ai-import" element={<AiImportPage />} />
            {/* Deprecated routes — redirect to the unified locations */}
            <Route path="/quality" element={<Navigate to="/production" replace />} />
            <Route path="/capacity" element={<Navigate to="/packing" replace />} />
            <Route path="/fabric-lines" element={<Navigate to="/inventory" replace />} />
            <Route path="/products/109-single-bed-fabrics" element={<Navigate to="/inventory" replace />} />
          </Route>
        </Route>
        <Route path="*" element={<DefaultLanding />} />
      </Routes>
    </Suspense>
  );
}
