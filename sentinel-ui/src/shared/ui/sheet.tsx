import * as React from "react";
import { cn } from "@/shared/lib/utils";

type SheetContextValue = {
  open: boolean;
  setOpen: (open: boolean) => void;
};

const SheetContext = React.createContext<SheetContextValue | null>(null);

function useSheetContext() {
  const ctx = React.useContext(SheetContext);
  if (!ctx) {
    throw new Error("Sheet components must be used inside <Sheet />");
  }
  return ctx;
}

type SheetProps = React.PropsWithChildren<{
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}>;

export function Sheet({
  children,
  open,
  defaultOpen = false,
  onOpenChange,
}: SheetProps) {
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen);
  const isControlled = open !== undefined;
  const currentOpen = isControlled ? open : internalOpen;

  const setOpen = React.useCallback(
    (next: boolean) => {
      if (!isControlled) {
        setInternalOpen(next);
      }
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange]
  );

  return (
    <SheetContext.Provider value={{ open: currentOpen, setOpen }}>
      {children}
    </SheetContext.Provider>
  );
}

export function SheetTrigger({
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const { setOpen } = useSheetContext();
  return <button className={className} onClick={() => setOpen(true)} type="button" {...props} />;
}

type SheetContentProps = React.HTMLAttributes<HTMLDivElement> & {
  side?: "left" | "right";
};

export function SheetContent({
  className,
  children,
  side = "right",
  ...props
}: SheetContentProps) {
  const { open, setOpen } = useSheetContext();
  if (!open) {
    return null;
  }

  return (
    <>
      <button
        aria-label="Close sheet"
        className="fixed inset-0 z-40 bg-black/40"
        onClick={() => setOpen(false)}
        type="button"
      />
      <div
        className={cn(
          "fixed top-0 z-50 h-screen w-[88vw] max-w-sm bg-background shadow-lg",
          side === "left" ? "left-0 border-r" : "right-0 border-l",
          className
        )}
        {...props}
      >
        {children}
      </div>
    </>
  );
}

export function SheetHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mb-2", className)} {...props} />;
}

export function SheetTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-base font-semibold", className)} {...props} />;
}

export function SheetDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

export function SheetClose({
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const { setOpen } = useSheetContext();
  return (
    <button
      className={className}
      onClick={() => setOpen(false)}
      type="button"
      {...props}
    />
  );
}
