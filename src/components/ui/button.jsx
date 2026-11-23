import { Slot } from "@radix-ui/react-slot";
import { buttonVariants } from "./button-variants";
import { cn } from "@/lib/utils";

function Button({ className, variant, size, asChild = false, ...props }) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

// shadcn/ui Button (new-york); variants live in button-variants.js.
export { Button };
