"use client";

import { useEffect } from "react";

export function ActiveTabScroller() {
  useEffect(() => {
    const activeTab = document.querySelector<HTMLElement>(
      ".project-tabs [aria-current='page']",
    );
    const navigation = activeTab?.closest<HTMLElement>(".project-tabs");
    if (!activeTab || !navigation) return;

    const centerActiveTab = () => {
      const centeredLeft =
        activeTab.offsetLeft - (navigation.clientWidth - activeTab.clientWidth) / 2;
      navigation.scrollTo({ left: Math.max(0, centeredLeft), behavior: "auto" });
    };

    centerActiveTab();
    const resizeObserver = new ResizeObserver(centerActiveTab);
    resizeObserver.observe(navigation);
    resizeObserver.observe(activeTab);
    return () => resizeObserver.disconnect();
  }, []);

  return null;
}
