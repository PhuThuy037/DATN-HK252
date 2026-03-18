import { type ReactNode } from "react";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

type SuggestionActionDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  isBusy: boolean;
  onConfirm: () => void;
  onClose: () => void;
  children?: ReactNode;
};

export function SuggestionActionDialog({
  open,
  title,
  description,
  confirmLabel,
  isBusy,
  onConfirm,
  onClose,
  children,
}: SuggestionActionDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-lg space-y-4 p-4">
        <div>
          <h3 className="text-base font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>

        {children}

        <div className="flex justify-end gap-2">
          <Button onClick={onClose} type="button" variant="outline">
            Cancel
          </Button>
          <Button disabled={isBusy} onClick={onConfirm} type="button">
            {confirmLabel}
          </Button>
        </div>
      </Card>
    </div>
  );
}
