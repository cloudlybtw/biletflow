import { useState } from "react";
import { enUS, kk, ru } from "date-fns/locale";
import { CalendarDays, Clock, X } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useLocale, t as translate } from "@/lib/locale";
import "./DateTimePicker.css";

const locales = { en: enUS, ru, kk };
const presets = ["10:00", "12:00", "15:00", "18:00", "19:00", "20:00"];
const pad = (n) => String(n).padStart(2, "0");

// Value format stays "YYYY-MM-DDTHH:mm" (what the forms already submit).
function splitValue(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value || "");
  return m
    ? { date: `${m[3]}.${m[2]}.${m[1]}`, time: `${m[4]}:${m[5]}` }
    : { date: "", time: "" };
}
// "24.11.2026", "24/11/26", "24.11" (this year) or "2026-11-24" -> Date.
function parseDate(text) {
  const iso = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(text.trim());
  const dmy = /^(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2}|\d{4}))?$/.exec(
    text.trim(),
  );
  let y, mo, d;
  if (iso) [y, mo, d] = [+iso[1], +iso[2], +iso[3]];
  else if (dmy) {
    [d, mo] = [+dmy[1], +dmy[2]];
    y = dmy[3]
      ? dmy[3].length === 2
        ? 2000 + +dmy[3]
        : +dmy[3]
      : new Date().getFullYear();
  } else return null;
  const date = new Date(y, mo - 1, d);
  return date.getMonth() === mo - 1 && date.getDate() === d ? date : null;
}
// "19", "930", "9:5", "19:30" -> "HH:MM".
function parseTime(text) {
  const t = text.trim();
  let h, m;
  const colon = /^(\d{1,2})[:.](\d{1,2})$/.exec(t);
  if (colon) [h, m] = [+colon[1], +colon[2]];
  else if (/^\d{1,4}$/.test(t))
    [h, m] = t.length <= 2 ? [+t, 0] : [+t.slice(0, -2), +t.slice(-2)];
  else return null;
  return h < 24 && m < 60 ? `${pad(h)}:${pad(m)}` : null;
}
const formatDate = (d) =>
  `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
// Typing helpers. Digits typed in a row get dots at 2 and 5 (05122026 ->
// 05.12.2026); anything the user separates themselves (6.12) is left alone.
const maskDate = (v) => {
  const text = v.replace(/[^\d./-]/g, "").slice(0, 10);
  const ownSeparators = [...text].some(
    (ch, i) => /[./-]/.test(ch) && !(ch === "." && (i === 2 || i === 5)),
  );
  if (ownSeparators) return text;
  const digits = text.replace(/\D/g, "").slice(0, 8);
  return [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)]
    .filter(Boolean)
    .join(".");
};
// Time is normalised on blur ("930" -> 09:30), so typing is never rewritten.
const maskTime = (v) => v.replace(/[^\d:.]/g, "").slice(0, 5);

// Typed date + typed time, with a calendar popover for picking the day.
// A hidden proxy input carries the field name, value and `required`.
export default function DateTimePicker({
  name,
  defaultValue = "",
  required = false,
  describedBy,
}) {
  const lang = useLocale();
  const initial = splitValue(defaultValue);
  const [dateText, setDateText] = useState(initial.date);
  const [timeText, setTimeText] = useState(initial.time);
  const [touched, setTouched] = useState({});
  const [open, setOpen] = useState(false);

  const date = parseDate(dateText);
  const time = parseTime(timeText);
  const value =
    date && time
      ? `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${time}`
      : "";
  const dateBad = touched.date && dateText !== "" && !date;
  const timeBad = touched.time && timeText !== "" && !time;

  function pickDay(day) {
    if (!day) return;
    setDateText(formatDate(day));
    // A fresh pick starts at 19:00, a typical event start.
    if (!time) setTimeText("19:00");
  }
  function commitDate() {
    setTouched((s) => ({ ...s, date: true }));
    if (date) {
      setDateText(formatDate(date));
      if (!timeText) setTimeText("19:00");
    }
  }
  function commitTime() {
    setTouched((s) => ({ ...s, time: true }));
    if (time) setTimeText(time);
  }

  return (
    <span className="bf-dt">
      <span className="bf-dt-field bf-dt-date">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="bf-dt-icon-btn"
              aria-label={translate("Open calendar")}
              title={translate("Open calendar")}
            >
              <CalendarDays aria-hidden="true" />
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="bf-dt-pop w-auto p-0">
            <div className="bf-dt-body">
              <Calendar
                mode="single"
                selected={date || undefined}
                onSelect={pickDay}
                defaultMonth={date || undefined}
                locale={locales[lang] || enUS}
                weekStartsOn={1}
              />
            </div>
            <div className="bf-dt-presets" aria-label={translate("Time")}>
              {presets.map((p) => (
                <Button
                  key={p}
                  type="button"
                  size="sm"
                  variant={time === p ? "default" : "ghost"}
                  aria-pressed={time === p}
                  onClick={() => setTimeText(p)}
                >
                  {p}
                </Button>
              ))}
            </div>
            <div className="bf-dt-foot">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setDateText("");
                  setTimeText("");
                }}
              >
                <X aria-hidden="true" />
                {translate("Clear")}
              </Button>
              <Button type="button" size="sm" onClick={() => setOpen(false)}>
                {translate("Done")}
              </Button>
            </div>
          </PopoverContent>
        </Popover>
        <input
          className="bf-dt-input"
          inputMode="numeric"
          autoComplete="off"
          placeholder={translate("DD.MM.YYYY")}
          aria-label={translate("Date")}
          aria-invalid={dateBad || undefined}
          aria-describedby={describedBy}
          value={dateText}
          onChange={(e) => setDateText(maskDate(e.target.value))}
          onBlur={commitDate}
        />
      </span>
      <span className="bf-dt-field bf-dt-time">
        <Clock aria-hidden="true" className="bf-dt-icon" />
        <input
          className="bf-dt-input"
          inputMode="numeric"
          autoComplete="off"
          placeholder={translate("HH:MM")}
          aria-label={translate("Time")}
          aria-invalid={timeBad || undefined}
          aria-describedby={describedBy}
          value={timeText}
          onChange={(e) => setTimeText(maskTime(e.target.value))}
          onBlur={commitTime}
        />
      </span>
      {(dateBad || timeBad) && (
        <span className="bf-dt-error" role="alert">
          {dateBad
            ? translate("Enter a date like 24.11.2026.")
            : translate("Enter a time like 19:30.")}
        </span>
      )}
      <input
        className="bf-dt-proxy"
        name={name}
        value={value}
        onChange={() => {}}
        required={required}
        tabIndex={-1}
        aria-hidden="true"
        autoComplete="off"
      />
    </span>
  );
}
