import { Navigate, createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/app/layouts/AppLayout";
import { LoginPage } from "@/pages/login/LoginPage";
import { RegisterPage } from "@/pages/register/RegisterPage";
import { OnboardingRuleSetPage } from "@/pages/onboarding/OnboardingRuleSetPage";
import { ChatPage } from "@/pages/chat/ChatPage";
import { AdminConversationsPage } from "@/pages/admin/AdminConversationsPage";
import { AdminConversationDetailPage } from "@/pages/admin/AdminConversationDetailPage";
import { AdminBlockMaskLogsPage } from "@/pages/admin/AdminBlockMaskLogsPage";
import { SystemPromptSettingsPage } from "@/features/settings/SystemPromptSettingsPage";
import { RulesPage } from "@/pages/settings/RulesPage";
import { SuggestionDetailPage } from "@/pages/suggestions/SuggestionDetailPage";
import { SuggestionsPage } from "@/pages/suggestions/SuggestionsPage";
import { AdminRoute } from "@/features/auth/components/AdminRoute";
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
        <AdminRoute>
          <RuleSetOnboardingRoute>
            <OnboardingRuleSetPage />
          </RuleSetOnboardingRoute>
        </AdminRoute>
      </ProtectedRoute>
    ),
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
        element: (
          <AdminRoute>
            <RuleSetAppRoute>
              <SystemPromptSettingsPage />
            </RuleSetAppRoute>
          </AdminRoute>
        ),
      },
      {
        path: "settings/rules",
        element: (
          <AdminRoute>
            <RuleSetAppRoute>
              <RulesPage />
            </RuleSetAppRoute>
          </AdminRoute>
        ),
      },
      {
        path: "suggestions",
        element: (
          <AdminRoute>
            <RuleSetAppRoute>
              <SuggestionsPage />
            </RuleSetAppRoute>
          </AdminRoute>
        ),
      },
      {
        path: "suggestions/:suggestionId",
        element: (
          <AdminRoute>
            <RuleSetAppRoute>
              <SuggestionDetailPage />
            </RuleSetAppRoute>
          </AdminRoute>
        ),
      },
      {
        path: "admin/conversations",
        element: (
          <AdminRoute>
            <AdminConversationsPage />
          </AdminRoute>
        ),
      },
      {
        path: "admin/conversations/:conversationId",
        element: (
          <AdminRoute>
            <AdminConversationDetailPage />
          </AdminRoute>
        ),
      },
      {
        path: "admin/logs/block-mask",
        element: (
          <AdminRoute>
            <AdminBlockMaskLogsPage />
          </AdminRoute>
        ),
      },
      {
        path: "*",
        element: <Navigate to="chat" replace />,
      },
    ],
  },
  {
    path: "*",
    element: <Navigate to="/login" replace />,
  },
]);
