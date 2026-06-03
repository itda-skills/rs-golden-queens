"use client";

// 모바일 드로어(좌측 사이드바)의 열림 상태를 헤더(☰ 버튼)와 사이드바가 공유한다.
// 데스크탑(lg+)에선 사이드바가 항상 고정이라 이 상태를 쓰지 않는다.

import { createContext, useContext, useState, type ReactNode } from "react";

const DrawerCtx = createContext<{
  open: boolean;
  setOpen: (v: boolean) => void;
} | null>(null);

export function DrawerProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <DrawerCtx.Provider value={{ open, setOpen }}>{children}</DrawerCtx.Provider>
  );
}

export function useDrawer() {
  const ctx = useContext(DrawerCtx);
  if (!ctx) throw new Error("useDrawer must be used within DrawerProvider");
  return ctx;
}
