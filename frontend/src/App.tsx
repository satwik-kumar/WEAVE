import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { AskBrainPage } from "./pages/AskBrainPage";
import "./App.css";
import { Icon } from "./components/Icon";
import { ThemeControl } from "./components/ThemeControl";

const HealthPage = lazy(() =>
  import("./pages/HealthPage").then((module) => ({
    default: module.HealthPage,
  })),
);
const OnboardingPage = lazy(() =>
  import("./pages/OnboardingPage").then((module) => ({
    default: module.OnboardingPage,
  })),
);

export default function App() {
  useEffect(() => {
    const pointer = () => {
      document.documentElement.dataset.input = "pointer";
    };
    const keyboard = () => {
      document.documentElement.dataset.input = "keyboard";
    };
    window.addEventListener("pointerdown", pointer, true);
    window.addEventListener("keydown", keyboard, true);
    return () => {
      window.removeEventListener("pointerdown", pointer, true);
      window.removeEventListener("keydown", keyboard, true);
    };
  }, []);
  return (
    <BrowserRouter>
      <aside className="app-sidebar">
        <NavLink className="brand-symbol" to="/" aria-label="WEAVE home">
          <Icon name="brain" size={25} />
        </NavLink>
        <nav aria-label="Workspace">
          <NavLink to="/" aria-label="Ask Brain" title="Ask Brain">
            <Icon name="chat" />
            <span className="nav-tooltip">Ask Brain</span>
          </NavLink>
          <NavLink
            to="/health"
            aria-label="Knowledge Health"
            title="Knowledge Health"
          >
            <Icon name="health" />
            <span className="nav-tooltip">Knowledge Health</span>
          </NavLink>
          <NavLink to="/onboarding" aria-label="Onboarding" title="Onboarding">
            <Icon name="book" />
            <span className="nav-tooltip">Onboarding</span>
          </NavLink>
        </nav>
        <span className="sidebar-footer" title="Engineering workspace">
          <Icon name="graph" />
        </span>
      </aside>
      <div className="app-content">
        <header className="app-header">
          <NavLink className="brand" to="/">
            WEAVE
          </NavLink>
          <span className="header-divider" />
          <span className="workspace-name">Engineering workspace</span>
          <span className="header-note">
            <Icon name="graph" size={14} /> Connected knowledge
          </span>
          <ThemeControl />
        </header>
        <Suspense fallback={<p role="status">Loading page?</p>}>
          <Routes>
            <Route path="/" element={<AskBrainPage />} />
            <Route path="/health" element={<HealthPage />} />
            <Route path="/onboarding" element={<OnboardingPage />} />
            <Route
              path="*"
              element={
                <main className="not-found">
                  <h1>Page unavailable</h1>
                  <a href="/">Return to Ask Brain</a>
                </main>
              }
            />
          </Routes>
        </Suspense>
      </div>
    </BrowserRouter>
  );
}
