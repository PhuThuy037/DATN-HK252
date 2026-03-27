import type { ReactNode } from "react";
import { AppButton } from "@/shared/ui/app-button";
import { AppModal } from "@/shared/ui/app-modal";

type ConfirmDialogProps = {
  open: boolean;
  title: ReactNode;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: "primary" | "danger";
  isBusy?: boolean;
  children?: ReactNode;
  onConfirm: () => void;
  onClose: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  confirmVariant = "primary",
  isBusy = false,
  children,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <AppModal
      description={description}
      footer={
        <div className="flex justify-end gap-2">
          <AppButton onClick={onClose} type="button" variant="secondary">
            {cancelLabel}
          </AppButton>
          <AppButton disabled={isBusy} onClick={onConfirm} type="button" variant={confirmVariant}>
            {confirmLabel}
          </AppButton>
        </div>
      }
      onClose={onClose}
      open={open}
      size="sm"
      title={title}
    >
      {children}
    </AppModal>
  );
}
