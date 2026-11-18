"use client";

import React from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/Auth";

function GuestBanner() {
  const { signOut } = useAuth();

  return (
    <div className="bg-muted/50 shrink-0 border-b">
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-center gap-x-3 gap-y-2 px-4 py-2">
        <span className="text-muted-foreground text-sm">
          Guest session — chats live only on this device until you create an
          account.
        </span>
        <Button
          asChild
          size="sm"
          type="button"
          variant="outline"
        >
          <Link href="/auth/sign-up">Create account</Link>
        </Button>
        <Button
          onClick={() => signOut()}
          size="sm"
          type="button"
          variant="ghost"
        >
          Sign out
        </Button>
      </div>
    </div>
  );
}

export { GuestBanner };
