import { useLocation } from "react-router-dom";
import { MenuIcon, MoonIcon, SunIcon } from "../ui/Icons";
import { useTheme } from "../../context/ThemeContext";

const names:Record<string,string> = {
  "/":"Home","/prepare/pdf":"Extract from PDF","/prepare/requirements":"Extract requirements","/prepare/chapters":"Extract chapters",
  "/review/compare-specifications":"Compare specification versions","/review/inconsistencies":"Check for Inconsistencies",
  "/review/quality":"Quality checker",
  "/verification/generate":"Generate vPlan","/verification/vplan":"vPlan","/verification/edge-cases":"Edge cases",
  "/verification/weak-language":"Weak language","/verification/coverage":"Coverage","/reports/metrics":"Usage and cost"
};

export default function TopBar({onMenu}:{onMenu:()=>void}) {
  const {pathname}=useLocation(); const {theme,toggleTheme}=useTheme();
  return <header className="topbar">
    <div className="topbar-start"><button className="icon-button mobile-menu" onClick={onMenu}><MenuIcon/></button><div><small>Specification workspace</small><strong>{names[pathname] ?? "Workspace"}</strong></div></div>
    <button className="theme-button" onClick={toggleTheme}>{theme==="light"?<MoonIcon/>:<SunIcon/>}<span>{theme==="light"?"Dark mode":"Light mode"}</span></button>
  </header>;
}
