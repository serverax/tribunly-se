"use client";

import Link from "next/link";
import { useEffect } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useUserStore } from "@/store/userStore";

export function SiteNav() {
  const { user, refresh } = useUserStore();

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const links = [
    { href: "/", label: "Home" },
    { href: "/intake", label: "Intake" },
    { href: "/diagnosis", label: "Diagnosis" },
    { href: "/dashboard", label: "Dashboard" },
    { href: "/workspace", label: "Workspace" },
    { href: "/documents", label: "Documents" },
    { href: "/payment", label: "Payment" },
    { href: "/handoff", label: "Handoff" },
  ];

  return (
    <header className="border-b border-border">
      <nav
        aria-label="Primary"
        className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-4 text-sm"
      >
        <span className="mr-2 font-semibold">LawApp</span>
        {links.map((l) => (
          <Link key={l.href} href={l.href} className="hover:text-primary">
            {l.label}
          </Link>
        ))}
        <LanguageSwitcher />
        <span className="ml-auto text-muted-foreground">
          {user?.email ? user.email : "Guest"}
        </span>
      </nav>
    </header>
  );
}
