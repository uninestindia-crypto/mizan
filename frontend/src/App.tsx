import { PlugZap } from "lucide-react";
import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { Layout } from "./components/Layout";
import { Button, EmptyState, Spinner } from "./components/ui";
import { useStatus } from "./lib/queries";
import { useResolvedTheme } from "./lib/theme";
import { Home } from "./pages/Home";

const Welcome = lazy(() => import("./pages/Welcome"));
const Markets = lazy(() => import("./pages/Markets"));
const Stock = lazy(() => import("./pages/Stock"));
const Lab = lazy(() => import("./pages/Lab"));
const LabNew = lazy(() => import("./pages/LabNew"));
const LabRun = lazy(() => import("./pages/LabRun"));
const Portfolio = lazy(() => import("./pages/Portfolio"));
const Paper = lazy(() => import("./pages/Paper"));
const PaperNew = lazy(() => import("./pages/PaperNew"));
const PaperBook = lazy(() => import("./pages/PaperBook"));
const Tools = lazy(() => import("./pages/Tools"));
const Settings = lazy(() => import("./pages/Settings"));
const Shariah = lazy(() => import("./pages/Shariah"));

function PageFallback() {
  return (
    <div className="flex h-64 items-center justify-center">
      <Spinner />
    </div>
  );
}

export function App() {
  const status = useStatus();
  const location = useLocation();
  useResolvedTheme(status.data?.settings.theme ?? "system");

  if (status.isPending) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Starting QuantOS" />
      </div>
    );
  }
  if (status.isError) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          art={<PlugZap className="size-10 text-ink-3" aria-hidden />}
          title="The QuantOS engine is not running"
          body="QuantOS runs a small engine on this computer. Close this window and open QuantOS again from the Start menu."
          action={<Button onClick={() => void status.refetch()}>Try again</Button>}
        />
      </div>
    );
  }

  const onboarding = !status.data.settings.onboarding_complete;
  if (onboarding && location.pathname !== "/welcome") return <Navigate to="/welcome" replace />;
  if (location.pathname === "/welcome") {
    return (
      <Suspense fallback={<PageFallback />}>
        <Welcome />
      </Suspense>
    );
  }

  return (
    <Layout>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/markets" element={<Markets />} />
          <Route path="/stock/:symbol" element={<Stock />} />
          <Route path="/lab" element={<Lab />} />
          <Route path="/lab/new/:templateId" element={<LabNew />} />
          <Route path="/lab/runs/:runId" element={<LabRun />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/paper" element={<Paper />} />
          <Route path="/paper/new" element={<PaperNew />} />
          <Route path="/paper/:id" element={<PaperBook />} />
          <Route path="/tools" element={<Navigate to="/tools/costs" replace />} />
          <Route path="/tools/:tool" element={<Tools />} />
          <Route path="/settings" element={<Navigate to="/settings/profile" replace />} />
          <Route path="/settings/:section" element={<Settings />} />
          <Route path="/shariah" element={<Shariah />} />
          <Route
            path="*"
            element={
              <EmptyState title="Page not found" body="That page does not exist." action={<Button onClick={() => history.back()}>Go back</Button>} />
            }
          />
        </Routes>
      </Suspense>
    </Layout>
  );
}
