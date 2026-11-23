import { useEffect, useRef, useState } from "react";
import { format } from "date-fns";
import { enUS, kk, ru } from "date-fns/locale";
import { CalendarDays, X } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useLocale, t as translate } from "@/lib/locale";
import { cn } from "@/lib/utils";
import "./DateTimePicker.css";

const locales = { en: enUS, ru, kk };
const hours = Array.from({ length: 24 }, (_, i) => i);
const minutes = Array.from({ length: 12 }, (_, i) => i * 5);
const pad = (n) => String(n).padStart(2, "0");

// "YYYY-MM-DDTHH:mm" (the datetime-local format the forms already submit).
function parse(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value || "");
  return m ? new Date(+m[1], m[2] - 1, +m[3], +m[4], +m[5]) : null;
}
function serialize(date) {
  return date
    ? `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
    : "";
}

// Date + time picker on shadcn Calendar/Popover. A text proxy input keeps the
// field name, value and `required` validation for the surrounding <form>.
export default function DateTimePicker({
  name,
  defaultValue = "",
  required = false,
  describedBy,
}) {
  const lang = useLocale();
  const locale = locales[lang] || enUS;
  const [value, setValue] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const date = parse(value);
  const hourList = useRef(null);
  const minuteList = useRef(null);

  // Keep the selected hour/minute in view (on open and after each pick).
  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => {
      for (const list of [hourList.current, minuteList.current])
        list
          ?.querySelector("[aria-pressed='true']")
          ?.scrollIntoView({ block: "nearest" });
    });
    return () => cancelAnimationFrame(frame);
  }, [open, value]);

  const update = (next) => setValue(serialize(next));
  const pickDay = (day) => {
    if (!day) return;
    const next = new Date(day);
    // A fresh pick starts at 19:00, a typical event start.
    next.setHours(date ? date.getHours() : 19, date ? date.getMinutes() : 0);
    update(next);
  };
  const pickTime = (h, m) => {
    const next = date ? new Date(date) : new Date();
    next.setHours(h ?? next.getHours(), m ?? next.getMinutes(), 0, 0);
    update(next);
  };

  return (
    <span className="bf-dt">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className={cn("bf-dt-trigger", !date && "is-empty")}
            aria-describedby={describedBy}
          >
            <CalendarDays aria-hidden="true" className="bf-dt-icon" />
            <span>
              {date
                ? format(date, "EEE, d MMM yyyy · HH:mm", { locale })
                : translate("Pick date and time")}
            </span>
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="bf-dt-pop w-auto p-0">
          <div className="bf-dt-body">
            <Calendar
              mode="single"
              selected={date || undefined}
              onSelect={pickDay}
              defaultMonth={date || undefined}
              locale={locale}
              weekStartsOn={1}
            />
            <div className="bf-dt-time" aria-label={translate("Time")}>
              <p className="bf-dt-time-label">{translate("Time")}</p>
              <div className="bf-dt-cols">
                <div ref={hourList} className="bf-dt-col" role="group">
                  {hours.map((h) => (
                    <Button
                      key={h}
                      type="button"
                      size="sm"
                      variant={date?.getHours() === h ? "default" : "ghost"}
                      aria-pressed={date?.getHours() === h}
                      onClick={() => pickTime(h, null)}
                    >
                      {pad(h)}
                    </Button>
                  ))}
                </div>
                <div ref={minuteList} className="bf-dt-col" role="group">
                  {minutes.map((m) => (
                    <Button
                      key={m}
                      type="button"
                      size="sm"
                      variant={date?.getMinutes() === m ? "default" : "ghost"}
                      aria-pressed={date?.getMinutes() === m}
                      onClick={() => pickTime(null, m)}
                    >
                      {pad(m)}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="bf-dt-foot">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => update(null)}
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
        className="bf-dt-proxy"
        name={name}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        required={required}
        tabIndex={-1}
        aria-hidden="true"
        autoComplete="off"
      />
    </span>
  );
}
