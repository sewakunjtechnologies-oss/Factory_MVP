import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { LoadingState } from "./components/LoadingState";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AppLayout } from "./layouts/AppLayout";

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
const ContractorsPage = lazy(() => import("./pages/ContractorsPage"));
const DispatchPage = lazy(() => import("./pages/DispatchPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const RemindersPage = lazy(() => import("./pages/RemindersPage"));
const AssistantPage = lazy(() => import("./pages/AssistantPage"));
const FabricLinesPage = lazy(() => import("./pages/FabricLinesPage"));
const AiImportPage = lazy(() => import("./pages/AiImportPage"));

export default function App() {
  return (
    <Suspense fallback={<div className="p-6"><LoadingState /></div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
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
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Suspense>
  );
}
