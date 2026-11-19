import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, lazy } from "react";
import { createRoot } from "react-dom/client";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import "./index.css";
import Layout from "./components/Layout";
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Analyze = lazy(() => import("./pages/Analyze"));
const Capture = lazy(() => import("./pages/Capture"));
const Verify = lazy(() => import("./pages/Verify"));
const CaseDetailPage = lazy(() => import("./pages/CaseDetail"));
const Cases = lazy(() => import("./pages/Cases"));
const IntegrityLab = lazy(() => import("./pages/IntegrityLab"));
const ModelLab = lazy(() => import("./pages/ModelLab"));
const ActivityPage = lazy(() => import("./pages/Activity"));
const About = lazy(() => import("./pages/About"));
const NotFound = lazy(() => import("./pages/NotFound"));

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 10_000 } } });

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    hydrateFallbackElement: <div />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <Dashboard /> },
      { path: "analyze", element: <Analyze /> },
      { path: "capture", element: <Capture /> },
      { path: "verify", element: <Verify /> },
      { path: "cases", element: <Cases /> },
      { path: "cases/:id", element: <CaseDetailPage /> },
      { path: "integrity-lab", element: <IntegrityLab /> },
      { path: "model-lab", element: <ModelLab /> },
      { path: "activity", element: <ActivityPage /> },
      { path: "about", element: <About /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
      <Toaster position="bottom-right" richColors closeButton toastOptions={{ style: { fontFamily: "var(--font-sans)" } }} />
    </QueryClientProvider>
  </StrictMode>,
);
