import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ThemeProvider } from "./context/ThemeContext";
import { WorkflowProvider } from "./context/WorkflowContext";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <WorkflowProvider>
          <App />
        </WorkflowProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>
);
