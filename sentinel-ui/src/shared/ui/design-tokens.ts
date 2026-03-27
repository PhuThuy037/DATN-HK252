export const designTokens = {
  colors: {
    primary: "hsl(var(--primary))",
    success: "hsl(var(--success))",
    warning: "hsl(var(--warning))",
    danger: "hsl(var(--danger))",
    muted: "hsl(var(--muted))",
  },
  spacing: {
    1: "var(--space-1)",
    2: "var(--space-2)",
    3: "var(--space-3)",
    4: "var(--space-4)",
    5: "var(--space-5)",
    6: "var(--space-6)",
    8: "var(--space-8)",
    10: "var(--space-10)",
  },
  radii: {
    sm: "var(--radius-sm)",
    md: "var(--radius-md)",
    lg: "var(--radius-lg)",
    xl: "var(--radius-xl)",
  },
  shadows: {
    sm: "var(--shadow-sm)",
    md: "var(--shadow-md)",
    lg: "var(--shadow-lg)",
  },
  typography: {
    display: "text-display",
    title: "text-title",
    heading: "text-heading",
    body: "text-body",
    label: "text-label",
    caption: "text-caption",
  },
} as const;

export const appSurfaceClassName = "app-card-surface";
export const appControlClassName = "app-control";
export const appSelectControlClassName = "app-select-control";
export const appModalPanelClassName = "app-modal-panel";
export const appCodeBlockClassName = "app-code-block";
export const appFieldLabelClassName = "app-field-label";
export const appFieldHelpTextClassName = "app-field-help";
export const appInlineErrorTextClassName = "app-inline-error";
export const appActionRowClassName = "app-action-row";
export const appAdvancedSectionClassName = "app-advanced-section";
