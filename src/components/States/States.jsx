import { useLocale } from "../../lib/locale";
import "./States.css";
const text = {
  en: {
    loading: "Loading…",
    retry: "Try again",
    errorTitle: "Something went wrong",
    errorBody: "We could not load this. Check your connection and try again.",
    emptyTitle: "Nothing here yet",
    notFoundTitle: "Page not found",
    notFoundBody: "The page you are looking for does not exist or has moved.",
    home: "Back to events",
  },
  ru: {
    loading: "Загрузка…",
    retry: "Повторить",
    errorTitle: "Что-то пошло не так",
    errorBody: "Не удалось загрузить. Проверьте соединение и повторите.",
    emptyTitle: "Пока пусто",
    notFoundTitle: "Страница не найдена",
    notFoundBody: "Такой страницы нет или она переехала.",
    home: "К афише",
  },
  kk: {
    loading: "Жүктелуде…",
    retry: "Қайталау",
    errorTitle: "Бірдеңе дұрыс болмады",
    errorBody: "Жүктеу мүмкін болмады. Байланысты тексеріп, қайталаңыз.",
    emptyTitle: "Әзірге бос",
    notFoundTitle: "Бет табылмады",
    notFoundBody: "Мұндай бет жоқ немесе көшірілген.",
    home: "Афишаға",
  },
};
export function EventCardSkeleton({ count = 4 }) {
  const t = text[useLocale()];
  return (
    <div className="state-grid" role="status" aria-label={t.loading}>
      {Array.from({ length: count }, (_, i) => (
        <div className="skeleton-card" key={i} aria-hidden="true">
          <div className="skeleton-image" />
          <div className="skeleton-line short" />
          <div className="skeleton-line" />
          <div className="skeleton-line medium" />
        </div>
      ))}
    </div>
  );
}
export function EmptyState({ title, body, action, onAction }) {
  const t = text[useLocale()];
  return (
    <div className="state-box" role="status">
      <h2>{title || t.emptyTitle}</h2>
      {body && <p>{body}</p>}
      {action && (
        <button className="button button-purple" onClick={onAction}>
          {action}
        </button>
      )}
    </div>
  );
}
export function ErrorState({ onRetry, title, body }) {
  const t = text[useLocale()];
  return (
    <div className="state-box" role="alert">
      <h2>{title || t.errorTitle}</h2>
      <p>{body || t.errorBody}</p>
      {onRetry && (
        <button className="button button-purple" onClick={onRetry}>
          {t.retry}
        </button>
      )}
    </div>
  );
}
export function NotFound() {
  const t = text[useLocale()];
  return (
    <div className="state-box">
      <h1>{t.notFoundTitle}</h1>
      <p>{t.notFoundBody}</p>
      <a className="button button-purple" href="#/events">
        {t.home}
      </a>
    </div>
  );
}
