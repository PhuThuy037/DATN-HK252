import { useState } from "react";
import { Menu, PanelRight, X } from "lucide-react";
import { Outlet, useParams } from "react-router-dom";
import { CompliancePanel } from "@/features/compliance/components/CompliancePanel";
import { ConversationSidebar } from "@/features/conversations/components/ConversationSidebar";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { Sheet, SheetContent } from "@/shared/ui/sheet";

export function AppLayout() {
  const { conversationId } = useParams();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isComplianceOpen, setIsComplianceOpen] = useState(false);

  return (
    <div className="relative h-screen overflow-hidden bg-background">
      <div className="hidden h-full grid-cols-[280px_minmax(0,1fr)_320px] overflow-hidden md:grid">
        <ConversationSidebar activeConversationId={conversationId} />

        <main className="min-w-0 overflow-hidden">
          <Outlet />
        </main>

        <div className="h-full overflow-y-auto border-l bg-muted/20 p-4">
          <CompliancePanel conversationId={conversationId} className="h-full" />
        </div>
      </div>

      <div className="relative flex h-full flex-col md:hidden">
        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>

        <div className="pointer-events-none absolute right-3 top-3 z-40 flex items-center gap-2">
          <Button
            className="pointer-events-auto h-9 w-9 rounded-full shadow-md"
            onClick={() => setIsSidebarOpen(true)}
            size="icon"
            type="button"
            variant="outline"
          >
            <Menu className="h-4 w-4" />
          </Button>
          <Button
            className="pointer-events-auto h-9 rounded-full px-3 shadow-md"
            onClick={() => setIsComplianceOpen((prev) => !prev)}
            size="sm"
            type="button"
            variant="outline"
          >
            {isComplianceOpen ? (
              <>
                <X className="mr-1 h-4 w-4" />
                Hide
              </>
            ) : (
              <>
                <PanelRight className="mr-1 h-4 w-4" />
                Compliance
              </>
            )}
          </Button>
        </div>
      </div>

      <Sheet onOpenChange={setIsSidebarOpen} open={isSidebarOpen}>
        <SheetContent className="w-[88vw] max-w-[320px] p-0" side="left">
          <ConversationSidebar
            activeConversationId={conversationId}
            className="h-full border-r-0"
            onConversationSelect={() => setIsSidebarOpen(false)}
          />
        </SheetContent>
      </Sheet>

      {isComplianceOpen && (
        <button
          aria-label="Close compliance panel overlay"
          className="absolute inset-0 z-20 bg-black/25 md:hidden"
          onClick={() => setIsComplianceOpen(false)}
          type="button"
        />
      )}

      <div
        className={cn(
          "absolute right-0 top-0 z-30 h-full w-[86vw] max-w-[360px] border-l bg-muted/30 p-3 shadow-xl transition-transform duration-200 md:hidden",
          isComplianceOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        <CompliancePanel conversationId={conversationId} className="h-full" />
      </div>
    </div>
  );
}
