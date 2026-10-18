import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { AskBrainPage } from "./pages/AskBrainPage";
import "./App.css";
import "./styles/workspace.css";
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
      <a className="skip-link" href="#main-content">
        Skip to workspace
      </a>
      <aside className="app-sidebar">
        <NavLink className="brand-symbol" to="/" aria-label="WEAVE home">
          <Icon name="brain" size={25} />
          <span>
            WEAVE<small>Company Brain</small>
          </span>
        </NavLink>
        <span className="nav-section-label">WORKSPACE</span>
        <nav aria-label="Workspace">
          <NavLink to="/" end aria-label="Ask Brain" title="Ask Brain">
            <Icon name="chat" />
            <span className="nav-label">Ask Brain</span>
            <span className="nav-tooltip">Ask Brain</span>
          </NavLink>
          <NavLink
            to="/health"
            aria-label="Knowledge Health"
            title="Knowledge Health"
          >
            <Icon name="health" />
            <span className="nav-label">Knowledge Health</span>
            <span className="nav-tooltip">Knowledge Health</span>
          </NavLink>
          <NavLink to="/onboarding" aria-label="Onboarding" title="Onboarding">
            <Icon name="book" />
            <span className="nav-label">Onboarding</span>
            <span className="nav-tooltip">Onboarding</span>
          </NavLink>
        </nav>
        <span className="sidebar-footer" title="Engineering workspace">
          <Icon name="graph" />
          <span>
            Engineering knowledge<small>Connected through evidence</small>
          </span>
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
        <div id="main-content" tabIndex={-1}>
          <Suspense
            fallback={
              <p className="loading" role="status">
                Loading workspace…
              </p>
            }
          >
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
      </div>
    </BrowserRouter>
  );
}
