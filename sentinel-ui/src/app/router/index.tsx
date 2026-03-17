import { Navigate, createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/app/layouts/AppLayout";
import { LoginPage } from "@/pages/login/LoginPage";
import { RegisterPage } from "@/pages/register/RegisterPage";
import { OnboardingRuleSetPage } from "@/pages/onboarding/OnboardingRuleSetPage";
import { ChatPage } from "@/pages/chat/ChatPage";
import { SystemPromptSettingsPage } from "@/features/settings/SystemPromptSettingsPage";
import { RulesPage } from "@/pages/settings/RulesPage";
import { SuggestionDetailPage } from "@/pages/suggestions/SuggestionDetailPage";
import { SuggestionsPage } from "@/pages/suggestions/SuggestionsPage";
import { PoliciesPage } from "@/pages/policies/PoliciesPage";
import { PolicyJobDetailPage } from "@/pages/policies/PolicyJobDetailPage";
import { GuestRoute } from "@/features/auth/components/GuestRoute";
import { ProtectedRoute } from "@/features/auth/components/ProtectedRoute";
import { RuleSetAppRoute } from "@/features/rules/components/RuleSetAppRoute";
import { RuleSetOnboardingRoute } from "@/features/rules/components/RuleSetOnboardingRoute";

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
    element: (
      <ProtectedRoute>
        <RuleSetOnboardingRoute>
          <OnboardingRuleSetPage />
        </RuleSetOnboardingRoute>
      </ProtectedRoute>
    ),
  },
  {
    path: "/app",
    element: (
      <ProtectedRoute>
        <RuleSetAppRoute>
          <AppLayout />
        </RuleSetAppRoute>
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="chat" replace />,
      },
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
      {
        path: "settings/rules",
        element: <RulesPage />,
      },
      {
        path: "suggestions",
        element: <SuggestionsPage />,
      },
      {
        path: "suggestions/:suggestionId",
        element: <SuggestionDetailPage />,
      },
      {
        path: "policies",
        element: <PoliciesPage />,
      },
      {
        path: "policies/jobs",
        element: <PoliciesPage />,
      },
      {
        path: "policies/jobs/:jobId",
        element: <PolicyJobDetailPage />,
      },
    ],
  },
  {
    path: "*",
    element: <Navigate to="/login" replace />,
  },
]);
