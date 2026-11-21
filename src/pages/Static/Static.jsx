import { useEffect } from "react";
import Navbar from "../../components/Navbar/Navbar";
import Arrow from "../../components/Icons/Arrow";
import { NotFound } from "../../components/States/States";
import { staticPages, organizerLanding } from "../../data/pages";
import { useLocale } from "../../lib/locale";
import "./Static.css";

const text = {
  en: {
    home: "Home",
    draft: "Draft: the final wording is approved by the product owner.",
    more: "More",
    how: "How it works",
    why: "Why BiletFlow",
    questions: "Questions?",
    faq: "Read the FAQ",
  },
  ru: {
    home: "Главная",
    draft: "Черновик: окончательную редакцию утверждает владелец продукта.",
    more: "Ещё",
    how: "Как это работает",
    why: "Почему BiletFlow",
    questions: "Есть вопросы?",
    faq: "Читать FAQ",
  },
  kk: {
    home: "Басты бет",
    draft: "Жоба: соңғы мәтінді өнім иесі бекітеді.",
    more: "Тағы",
    how: "Бұл қалай жұмыс істейді",
    why: "Неге BiletFlow",
    questions: "Сұрақ бар ма?",
    faq: "FAQ оқу",
  },
};

// Static pages: #/cms/{slug} and the organizer landing #/for/organizers.
export default function Static({ path }) {
  const lang = useLocale();
  const t = text[lang];
  const organizers = path === "/for/organizers";
  const slug = organizers ? null : path.split("/")[2];
  const page = organizers ? organizerLanding : staticPages[slug];
  const title = page?.title[lang];

  useEffect(() => {
    if (title) document.title = `${title} | BiletFlow`;
  }, [title]);

  if (!page)
    return (
      <>
        <Navbar />
        <main className="page-width">
          <NotFound />
        </main>
      </>
    );

  return (
    <>
      <Navbar />
      <main className="static page-width">
        <nav className="crumbs" aria-label="Breadcrumb">
          <a href="/">{t.home}</a>
          <span aria-hidden="true">/</span>
          <span aria-current="page">{title}</span>
        </nav>
        <header className="static-head">
          <h1>{title}</h1>
          <p>{page.lede[lang]}</p>
          {organizers && (
            <a className="static-button" href="#/organizer">
              {page.cta[lang]}
              <Arrow size={16} />
            </a>
          )}
        </header>

        {organizers ? (
          <Landing page={page} lang={lang} t={t} />
        ) : (
          <div className="static-body">
            <article className="static-article">
              {page.draft && <p className="static-draft">{t.draft}</p>}
              {page.sections?.map((s) => (
                <section key={s.h.en}>
                  <h2>{s.h[lang]}</h2>
                  <p>{s.p[lang]}</p>
                  {s.link && (
                    <a className="static-link" href={`#${s.link.to}`}>
                      {s.link[lang]}
                      <Arrow size={15} />
                    </a>
                  )}
                </section>
              ))}
              {page.faq && (
                <div className="static-faq">
                  {page.faq.map((item) => (
                    <details key={item.q.en}>
                      <summary>
                        {item.q[lang]}
                        <span aria-hidden="true">+</span>
                      </summary>
                      <p>{item.a[lang]}</p>
                    </details>
                  ))}
                </div>
              )}
            </article>
            <aside className="static-side" aria-label={t.more}>
              <h2>{t.more}</h2>
              <ul>
                {Object.entries(staticPages)
                  .filter(([key]) => key !== slug)
                  .map(([key, other]) => (
                    <li key={key}>
                      <a href={`#/cms/${key}`}>{other.title[lang]}</a>
                    </li>
                  ))}
                <li>
                  <a href="#/for/organizers">{organizerLanding.title[lang]}</a>
                </li>
              </ul>
            </aside>
          </div>
        )}
      </main>
    </>
  );
}

function Landing({ page, lang, t }) {
  return (
    <>
      <section className="static-block" aria-labelledby="why">
        <h2 id="why" className="static-label">
          {t.why}
        </h2>
        <div className="static-benefits">
          {page.benefits.map((b, i) => (
            <div key={b.h.en} className="static-benefit">
              <span aria-hidden="true">{String(i + 1).padStart(2, "0")}</span>
              <h3>{b.h[lang]}</h3>
              <p>{b.p[lang]}</p>
            </div>
          ))}
        </div>
      </section>
      <section className="static-block" aria-labelledby="how">
        <h2 id="how" className="static-label">
          {t.how}
        </h2>
        <ol className="static-steps">
          {page.steps.map((step) => (
            <li key={step.en}>{step[lang]}</li>
          ))}
        </ol>
      </section>
      <section className="static-cta">
        <h2>{t.questions}</h2>
        <div>
          <a className="static-button" href="#/organizer">
            {page.cta[lang]}
            <Arrow size={16} />
          </a>
          <a className="static-button static-button-ghost" href="#/cms/faq">
            {t.faq}
          </a>
        </div>
      </section>
    </>
  );
}
