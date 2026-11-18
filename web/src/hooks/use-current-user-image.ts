"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/providers/Auth";

export const useCurrentUserImage = () => {
  const [image, setImage] = useState<string | null>(null);
  const { session } = useAuth();

  useEffect(() => {
    if (session?.user) {
      setImage(session.user.attributes?.picture ?? null);
    } else {
      setImage(null);
    }
  }, [session]);

  return image;
};
