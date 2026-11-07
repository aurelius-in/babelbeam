import { Route, Routes } from "react-router-dom";
import { SimulatedModeBanner } from "../components/SimulatedModeBanner";
import { SiteHeader } from "../components/Shell";
import { LandingPage } from "../features/landing/LandingPage";
import {
  DashboardPage,
  HelpPage,
  HowToPage,
  InstallPage,
  JoinPage,
  LoginPage,
  PricingPage,
} from "../features/pages/InfoPages";
import { LessonReviewPage, ShareLessonPage } from "../features/lessons/LessonReview";
import { usePublicConfig } from "../lib/usePublicConfig";
import { LocaleProvider } from "./i18n";

function Frame() {
  const { config, fetchFailed } = usePublicConfig();

  return (
    <div className="page">
      <SimulatedModeBanner config={config} fetchFailed={fetchFailed} />
      <SiteHeader />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/how" element={<HowToPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/install" element={<InstallPage />} />
        <Route path="/join" element={<JoinPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="/app" element={<DashboardPage />} />
        <Route path="/lessons/:lessonId" element={<LessonReviewPage />} />
        <Route path="/share/:shareToken" element={<ShareLessonPage />} />
      </Routes>
    </div>
  );
}

export function App() {
  return (
    <LocaleProvider>
      <Frame />
    </LocaleProvider>
  );
}
