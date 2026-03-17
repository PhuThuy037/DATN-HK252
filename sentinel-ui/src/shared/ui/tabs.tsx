import * as React from "react";
import { cn } from "@/shared/lib/utils";

type TabsContextValue = {
  value: string;
  setValue: (value: string) => void;
};

const TabsContext = React.createContext<TabsContextValue | null>(null);

function useTabsContext() {
  const ctx = React.useContext(TabsContext);
  if (!ctx) {
    throw new Error("Tabs components must be used inside <Tabs />");
  }
  return ctx;
}

type TabsProps = React.HTMLAttributes<HTMLDivElement> & {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
};

export function Tabs({
  className,
  value,
  defaultValue = "",
  onValueChange,
  children,
  ...props
}: TabsProps) {
  const [internalValue, setInternalValue] = React.useState(defaultValue);
  const isControlled = value !== undefined;
  const currentValue = isControlled ? value : internalValue;

  const setValue = React.useCallback(
    (next: string) => {
      if (!isControlled) {
        setInternalValue(next);
      }
      onValueChange?.(next);
    },
    [isControlled, onValueChange]
  );

  return (
    <TabsContext.Provider value={{ value: currentValue, setValue }}>
      <div className={cn("space-y-2", className)} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  );
}

export function TabsList({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("inline-flex rounded-md bg-muted p-1", className)}
      {...props}
    />
  );
}

type TabsTriggerProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  value: string;
};

export function TabsTrigger({
  className,
  value,
  ...props
}: TabsTriggerProps) {
  const { value: currentValue, setValue } = useTabsContext();
  const isActive = currentValue === value;

  return (
    <button
      className={cn(
        "rounded-sm px-3 py-1.5 text-sm transition-colors",
        isActive ? "bg-background shadow-sm" : "hover:bg-background/60",
        className
      )}
      onClick={() => setValue(value)}
      type="button"
      {...props}
    />
  );
}

type TabsContentProps = React.HTMLAttributes<HTMLDivElement> & {
  value: string;
};

export function TabsContent({
  className,
  value,
  children,
  ...props
}: TabsContentProps) {
  const { value: currentValue } = useTabsContext();
  if (currentValue !== value) {
    return null;
  }
  return (
    <div className={cn("rounded-md border p-3", className)} {...props}>
      {children}
    </div>
  );
}
