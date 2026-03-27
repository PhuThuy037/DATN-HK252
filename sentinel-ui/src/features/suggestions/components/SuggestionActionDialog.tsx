import type { ReactNode } from "react";
import { AppButton } from "@/shared/ui/app-button";
import { AppModal } from "@/shared/ui/app-modal";

type SuggestionActionDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  confirmVariant?: "primary" | "secondary" | "danger" | "ghost";
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
  confirmVariant = "primary",
  isBusy,
  onConfirm,
  onClose,
  children,
}: SuggestionActionDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <AppModal
      description={description}
      footer={
        <div className="flex justify-end gap-2">
          <AppButton onClick={onClose} type="button" variant="secondary">
            Cancel
          </AppButton>
          <AppButton disabled={isBusy} onClick={onConfirm} type="button" variant={confirmVariant}>
            {confirmLabel}
          </AppButton>
        </div>
      }
      onClose={onClose}
      open={open}
      size="md"
      title={title}
    >
      {children}
    </AppModal>
  );
}
