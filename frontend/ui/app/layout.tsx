import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RecoverIQ | AI Revenue Recovery",
  description: "Bounded, auditable revenue recovery for Razorpay",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
