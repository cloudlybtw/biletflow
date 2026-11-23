import { ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker, getDefaultClassNames } from "react-day-picker";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button-variants";

// shadcn/ui Calendar (new-york, react-day-picker v9), BiletFlow accents:
// selected day is black/white per theme, today gets a yellow dot.
function Calendar({ className, classNames, showOutsideDays = true, ...props }) {
  const d = getDefaultClassNames();
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("p-1", className)}
      classNames={{
        root: cn("w-fit", d.root),
        months: cn("relative flex flex-col gap-4", d.months),
        month: cn("flex w-full flex-col gap-3", d.month),
        nav: cn(
          "absolute inset-x-0 top-0 flex w-full items-center justify-between",
          d.nav,
        ),
        button_previous: cn(
          buttonVariants({ variant: "ghost", size: "icon" }),
          "size-8 rounded-full p-0 aria-disabled:opacity-40",
          d.button_previous,
        ),
        button_next: cn(
          buttonVariants({ variant: "ghost", size: "icon" }),
          "size-8 rounded-full p-0 aria-disabled:opacity-40",
          d.button_next,
        ),
        month_caption: cn(
          "flex h-8 w-full items-center justify-center px-8",
          d.month_caption,
        ),
        caption_label: cn(
          "text-[13px] font-bold uppercase tracking-[0.06em] select-none",
          d.caption_label,
        ),
        month_grid: cn("w-full border-collapse", d.month_grid),
        weekdays: cn("flex", d.weekdays),
        weekday: cn(
          "w-9 select-none text-center text-[11px] font-bold uppercase text-muted-foreground",
          d.weekday,
        ),
        week: cn("mt-1 flex w-full", d.week),
        day: cn("relative size-9 p-0 text-center text-sm select-none", d.day),
        day_button: cn(
          buttonVariants({ variant: "ghost" }),
          "size-9 rounded-full p-0 font-normal tabular-nums",
        ),
        today: cn(
          "font-bold after:absolute after:bottom-1 after:left-1/2 after:size-1 after:-translate-x-1/2 after:rounded-full after:bg-highlight",
          d.today,
        ),
        // v9 marks the cell, not the button, as selected.
        selected: cn(
          "[&>button]:bg-primary [&>button]:font-bold [&>button]:text-primary-foreground [&>button:hover]:bg-primary",
          d.selected,
        ),
        outside: cn("text-muted-foreground opacity-50", d.outside),
        disabled: cn("text-muted-foreground opacity-40", d.disabled),
        hidden: cn("invisible", d.hidden),
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation, className: c, ...rest }) =>
          orientation === "left" ? (
            <ChevronLeft className={cn("size-4", c)} {...rest} />
          ) : (
            <ChevronRight className={cn("size-4", c)} {...rest} />
          ),
      }}
      {...props}
    />
  );
}

export { Calendar };
