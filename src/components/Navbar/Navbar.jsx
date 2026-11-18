import { useState } from "react";
import { cities, cityLabel } from "../../data/i18n";
import { menuCategories } from "../../data/categories";
import { useLocale, setLocale } from "../../lib/locale";
import { useCity } from "../../lib/city";
import { useSession } from "../../lib/session-context";
import { logout } from "../../lib/client";
import "./Navbar.css";
const text = {
  en: {
    search: "Search events",
    city: "City",
    allCities: "All cities",
    tickets: "My tickets",
    organizers: "For organizers",
    signIn: "Sign in",
    register: "Register",
    account: "My account",
    organizer: "Organizer workspace",
    admin: "Platform admin",
    signOut: "Sign out",
    notifications: "Notifications",
    categories: "Event categories",
    skip: "Skip to content",
    language: "Language",
    menu: "Account menu",
    logoutFailed: "Signed out locally. Server logout could not be confirmed.",
  },
  ru: {
    search: "Поиск событий",
    city: "Город",
    allCities: "Все города",
    tickets: "Мои билеты",
    organizers: "Организаторам",
    signIn: "Войти",
    register: "Регистрация",
    account: "Мой аккаунт",
    organizer: "Кабинет организатора",
    admin: "Админ платформы",
    signOut: "Выйти",
    notifications: "Уведомления",
    categories: "Категории событий",
    skip: "Перейти к содержимому",
    language: "Язык",
    menu: "Меню аккаунта",
    logoutFailed: "Вы вышли локально. Выход на сервере не подтверждён.",
  },
  kk: {
    search: "Іс-шараларды іздеу",
    city: "Қала",
    allCities: "Барлық қалалар",
    tickets: "Менің билеттерім",
    organizers: "Ұйымдастырушыларға",
    signIn: "Кіру",
    register: "Тіркелу",
    account: "Менің аккаунтым",
    organizer: "Ұйымдастырушы кабинеті",
    admin: "Платформа әкімшісі",
    signOut: "Шығу",
    notifications: "Хабарландырулар",
    categories: "Іс-шара санаттары",
    skip: "Мазмұнға өту",
    language: "Тіл",
    menu: "Аккаунт мәзірі",
    logoutFailed: "Жергілікті шықтыңыз. Серверде шығу расталмады.",
  },
};
const here = () => location.hash.replace(/^#/, "");
export default function Navbar({ onSignIn }) {
  const lang = useLocale();
  const t = text[lang];
  const { user } = useSession() || {};
  const [city, setCity] = useCity();
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const route = here();
  const workspace = /^\/(organizer|admin)/.test(route);
  const activeCategory = route.startsWith("/category/")
    ? route.split("/")[2]?.split("?")[0]
    : "";
  function submit() {
    location.hash = `/search?q=${encodeURIComponent(q.trim())}`;
  }
  async function signOut() {
    try {
      await logout();
      location.hash = "/login";
    } catch {
      setError(t.logoutFailed);
    }
  }
  return (
    <header className="site-header">
      <button
        className="skip-link"
        onClick={() => {
          const main = document.querySelector("main");
          if (main) {
            main.tabIndex = -1;
            main.focus();
          }
        }}
      >
        {t.skip}
      </button>
      <nav className="nav-inner" aria-label="BiletFlow">
        <a href="/" className="wordmark" aria-label="BiletFlow">
          <span className="brand-icon" aria-hidden="true">
            b<span>f</span>
          </span>
          BiletFlow<span className="brand-dot">.</span>
        </a>
        <div className="nav-search" role="search">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            aria-hidden="true"
          >
            <circle cx="10.5" cy="10.5" r="6.5" />
            <path d="m16 16 5 5" />
          </svg>
          <input
            type="search"
            aria-label={t.search}
            placeholder={t.search}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
        </div>
        <label className="nav-city">
          <span className="visually-hidden">{t.city}</span>
          <span aria-hidden="true">⌖</span>
          <select value={city} onChange={(e) => setCity(e.target.value)}>
            <option value="">{t.allCities}</option>
            {Object.keys(cities).map((c) => (
              <option key={c} value={c}>
                {cityLabel(c, lang)}
              </option>
            ))}
          </select>
        </label>
        <label className="nav-lang">
          <span className="visually-hidden">{t.language}</span>
          <select value={lang} onChange={(e) => setLocale(e.target.value)}>
            <option value="kk">ҚАЗ</option>
            <option value="ru">RU</option>
            <option value="en">EN</option>
          </select>
        </label>
        <div className="nav-actions">
          <a className="nav-link" href="#/account/tickets">
            {t.tickets}
          </a>
          <a className="nav-link nav-organizers" href="#/for/organizers">
            {t.organizers}
          </a>
          {user ? (
            <>
              <a
                className="nav-bell"
                href="#/account/notifications"
                aria-label={t.notifications}
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  aria-hidden="true"
                >
                  <path d="M6 9a6 6 0 1 1 12 0c0 6 2 7 2 7H4s2-1 2-7Zm4 10a2 2 0 0 0 4 0" />
                </svg>
              </a>
              <details className="user-menu">
                <summary aria-label={t.menu}>{user.full_name}</summary>
                <div>
                  <a href="#/account">{t.account}</a>
                  <a href="#/organizer">{t.organizer}</a>
                  {user.platform_role === "platform_admin" && (
                    <a href="#/admin">{t.admin}</a>
                  )}
                  <button onClick={signOut}>{t.signOut}</button>
                </div>
              </details>
            </>
          ) : onSignIn ? (
            <button className="sign-in" onClick={onSignIn}>
              {t.signIn}
            </button>
          ) : (
            <a className="sign-in" href="#/login">
              {t.signIn}
            </a>
          )}
        </div>
      </nav>
      {!workspace && (
        <nav className="category-nav" aria-label={t.categories}>
          <ul className="category-nav-inner">
            {menuCategories.map((c) => (
              <li key={c.slug}>
                <a
                  href={`#/category/${c.slug}`}
                  aria-current={activeCategory === c.slug ? "page" : undefined}
                >
                  {c.label[lang]}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      )}
      {error && (
        <p role="alert" className="nav-error">
          {error}
        </p>
      )}
    </header>
  );
}
