import "./globals.css";

export const metadata = {
  title: "PDF Editor",
  description: "Free PDF tools: merge, split, compress, rotate, convert",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">{children}</body>
    </html>
  );
}
