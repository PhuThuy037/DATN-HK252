import { Navigate, createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/app/layouts/AppLayout";
import { LoginPage } from "@/pages/login/LoginPage";
import { RegisterPage } from "@/pages/register/RegisterPage";
import { OnboardingRuleSetPage } from "@/pages/onboarding/OnboardingRuleSetPage";
import { ChatPage } from "@/pages/chat/ChatPage";
import { SystemPromptSettingsPage } from "@/features/settings/SystemPromptSettingsPage";
import { GuestRoute } from "@/features/auth/components/GuestRoute";
import { ProtectedRoute } from "@/features/auth/components/ProtectedRoute";

export const appRouter = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/login" replace />,
  },
  {
    path: "/login",
    element: (
      <GuestRoute>
        <LoginPage />
      </GuestRoute>
    ),
  },
  {
    path: "/register",
    element: (
      <GuestRoute>
        <RegisterPage />
      </GuestRoute>
    ),
  },
  {
    path: "/onboarding/rule-set",
    element: <OnboardingRuleSetPage />,
  },
  {
    path: "/app",
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        path: "chat",
        element: <ChatPage />,
      },
      {
        path: "chat/:conversationId",
        element: <ChatPage />,
      },
      {
        path: "settings/system-prompt",
        element: <SystemPromptSettingsPage />,
      },
    ],
  },
  {
    path: "*",
    element: <Navigate to="/login" replace />,
  },
]);
