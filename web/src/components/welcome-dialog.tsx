import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

interface WelcomeDialogProps {
  onStart: () => void;
}

function WelcomeDialog({ onStart }: WelcomeDialogProps) {
  return (
    <div className="flex min-h-screen w-full items-center justify-center p-4">
      <div className="animate-in fade-in-0 zoom-in-95 bg-background flex max-w-3xl flex-col rounded-lg border shadow-lg">
        <div className="mt-14 flex flex-col gap-2 border-b p-6">
          <div className="flex flex-col items-start gap-2">
            <h1 className="text-xl font-semibold tracking-tight">Agent Chat</h1>
          </div>
          <p className="text-muted-foreground">Welcome to my Agent Chat!</p>
        </div>
        <div className="bg-muted/50 flex flex-col gap-6 p-6">
          <div className="mt-2 flex flex-wrap justify-end gap-2">
            <Button
              type="button"
              size="lg"
              onClick={() => onStart()}
            >
              Start
              <ArrowRight className="size-5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export { WelcomeDialog };
