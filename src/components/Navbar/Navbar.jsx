import { cities, cityLabel } from "../../data/i18n";
import "./Navbar.css";
export default function Navbar({ t, lang, setLang, city, setCity, onSignIn }) {
  return (
    <header className="site-header">
      <nav className="nav-inner" aria-label={t.discover}>
        <a href="#home" className="wordmark" aria-label="BiletFlow">
          <span className="brand-icon" aria-hidden="true">
            b<span>f</span>
          </span>
          BiletFlow<span className="brand-dot">.</span>
        </a>
        <label className="nav-city">
          <span aria-hidden="true">⌖</span>
          <select
            aria-label={t.city}
            value={city}
            onChange={(e) => setCity(e.target.value)}
          >
            <option value="">{t.allCities}</option>
            {Object.keys(cities).map((c) => (
              <option key={c} value={c}>
                {cityLabel(c, lang)}
              </option>
            ))}
          </select>
        </label>
        <div className="nav-links">
          <a className="nav-active" href="#discover">
            {t.discover}
          </a>
          <a href="#organizers">{t.organizers}</a>
        </div>
        <div className="nav-actions">
          <select
            aria-label="Language / Язык / Тіл"
            value={lang}
            onChange={(e) => setLang(e.target.value)}
          >
            <option value="en">EN</option>
            <option value="ru">RU</option>
            <option value="kk">ҚАЗ</option>
          </select>
          <button className="sign-in" onClick={onSignIn}>
            {t.signIn}
            <span aria-hidden="true"> ↗</span>
          </button>
        </div>
      </nav>
    </header>
  );
}
