import logoOnDark from "../../assets/logo-on-dark.png";
import logoOnLight from "../../assets/logo-on-light.png";
import "./Logo.css";

// Both variants are rendered; CSS shows the one that matches the active theme
// (light is the default, html[data-theme="dark"] on discovery pages).
export default function Logo({ className = "" }) {
  return (
    <span className={`bf-logo ${className}`.trim()}>
      <img className="bf-logo-light" src={logoOnLight} alt="" width="1453" height="280" />
      <img className="bf-logo-dark" src={logoOnDark} alt="" width="1453" height="280" />
    </span>
  );
}
