"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/providers/Auth";

export const useCurrentUserName = () => {
  const [name, setName] = useState<string | null>(null);
  const { session } = useAuth();

  useEffect(() => {
    if (session?.user) {
      setName(
        session.user.attributes?.name ??
          session.user.attributes?.preferred_username ??
          session.user.username ??
          "?",
      );
    } else {
      setName("?");
    }
  }, [session]);

  return name || "?";
};
