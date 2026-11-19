import { useEffect, useId, useRef, useState } from "react";
import "./Dropdown.css";

// Styled replacement for <select>: a button that opens a dark listbox.
// options: [{ value, label, hint? }]. Keyboard: arrows/Home/End move,
// Enter/Space picks, Escape/Tab close. `variant` is "pill" or "plain".
export default function Dropdown({
  value,
  options,
  onChange,
  label,
  display,
  icon,
  variant = "pill",
  align = "right",
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef(null);
  const list = useRef(null);
  const button = useRef(null);
  const id = useId();
  const index = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );
  const current = options[index];

  useEffect(() => {
    if (!open) return;
    list.current?.focus();
    const away = (e) => {
      if (!root.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);

  function toggle() {
    setActive(index);
    setOpen((o) => !o);
  }
  function choose(next) {
    onChange(next);
    setOpen(false);
    button.current?.focus();
  }
  function onKey(e) {
    const last = options.length - 1;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (i + step + options.length) % options.length);
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      setActive(e.key === "Home" ? 0 : last);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      choose(options[active].value);
    } else if (e.key === "Escape" || e.key === "Tab") {
      setOpen(false);
      if (e.key === "Escape") button.current?.focus();
    }
  }

  return (
    <div className={`dropdown dropdown-${variant}`} ref={root}>
      <button
        ref={button}
        type="button"
        className="dropdown-button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={id}
        aria-label={`${label}: ${current?.label ?? ""}`}
        onClick={toggle}
      >
        {icon}
        <span className="dropdown-value">{display ?? current?.label}</span>
        <svg
          className="dropdown-chevron"
          width="10"
          height="6"
          viewBox="0 0 10 6"
          fill="none"
          aria-hidden="true"
        >
          <path d="m1 1 4 4 4-4" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      </button>
      {open && (
        <ul
          ref={list}
          id={id}
          role="listbox"
          tabIndex={-1}
          aria-label={label}
          aria-activedescendant={`${id}-${active}`}
          className={`dropdown-list dropdown-list-${align}`}
          onKeyDown={onKey}
        >
          {options.map((o, i) => (
            <li
              key={o.value}
              id={`${id}-${i}`}
              role="option"
              aria-selected={o.value === value}
              className={i === active ? "is-active" : undefined}
              onPointerEnter={() => setActive(i)}
              onClick={() => choose(o.value)}
            >
              <span>{o.label}</span>
              {o.hint && <small>{o.hint}</small>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
