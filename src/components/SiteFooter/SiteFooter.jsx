import { useLocale } from "../../lib/locale";
import "./SiteFooter.css";
import Logo from "../Logo/Logo";
const text = {
  en: {
    tagline: "Made for going out. Made for Kazakhstan.",
    about: "About",
    organizers: "For organizers",
    docs: "Documents",
    terms: "Public offer",
    privacy: "Privacy policy",
    faq: "FAQ",
    contacts: "Contacts",
    help: "Help",
    company: "Company",
    timezone: "All times: Asia/Almaty (UTC+5)",
  },
  ru: {
    tagline: "Ближе к событиям. Ближе к Казахстану.",
    about: "О нас",
    organizers: "Организаторам",
    docs: "Документы",
    terms: "Публичная оферта",
    privacy: "Политика конфиденциальности",
    faq: "Вопросы и ответы",
    contacts: "Контакты",
    help: "Помощь",
    company: "Компания",
    timezone: "Все время: Asia/Almaty (UTC+5)",
  },
  kk: {
    tagline: "Қазақстандағы жарқын сәттер үшін.",
    about: "Біз туралы",
    organizers: "Ұйымдастырушыларға",
    docs: "Құжаттар",
    terms: "Жария оферта",
    privacy: "Құпиялылық саясаты",
    faq: "Жиі қойылатын сұрақтар",
    contacts: "Байланыс",
    help: "Көмек",
    company: "Компания",
    timezone: "Барлық уақыт: Asia/Almaty (UTC+5)",
  },
};
export default function SiteFooter() {
  const t = text[useLocale()];
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="footer-brand">
          <a className="wordmark" href="/">
            <Logo />
          </a>
          <p>{t.tagline}</p>
        </div>
        <nav aria-label={t.company}>
          <h2>{t.company}</h2>
          <a href="#/cms/about">{t.about}</a>
          <a href="#/for/organizers">{t.organizers}</a>
          <a href="#/cms/contacts">{t.contacts}</a>
        </nav>
        <nav aria-label={t.help}>
          <h2>{t.help}</h2>
          <a href="#/cms/faq">{t.faq}</a>
          <a href="#/account/support">{t.help}</a>
        </nav>
        <nav aria-label={t.docs}>
          <h2>{t.docs}</h2>
          <a href="#/cms/agreement">{t.terms}</a>
          <a href="#/cms/privacy-policy">{t.privacy}</a>
        </nav>
      </div>
      <div className="site-footer-bottom">
        <small>© {new Date().getFullYear()} BiletFlow</small>
        <small>{t.timezone}</small>
      </div>
    </footer>
  );
}
