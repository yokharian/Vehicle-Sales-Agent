"use client";

import dynamic from "next/dynamic";
import React, { useState } from "react";

import { ChatShell } from "@/components/assistant-ui/chat-shell";
import { WelcomeDialog } from "@/components/welcome-dialog";
import { AuthProvider } from "@/providers/Auth";
import { RuntimeProvider } from "@/providers/runtime";

const Gate = dynamic(() => import("@/components/gate").then((m) => m.Gate), {
  ssr: false,
});

export default function Page(): React.ReactNode {
  const [mode, setMode] = useState<"member" | null>(null);

  const app = (
    <RuntimeProvider>
      <ChatShell />
    </RuntimeProvider>
  );

  return (
    <AuthProvider>
      <React.Suspense fallback={<div>Loading (layout)...</div>}>
        {mode === null ? (
          <WelcomeDialog onStart={() => setMode("member")} />
        ) : (
          <Gate>{app}</Gate>
        )}
      </React.Suspense>
    </AuthProvider>
  );
}
