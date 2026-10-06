import { Link } from "react-router";

export function LogoMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <defs>
        <linearGradient id="ll-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7c7cf0" />
          <stop offset="1" stopColor="#4c4cc4" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#ll-logo)" />
      <circle cx="14.5" cy="14.5" r="6.5" fill="none" stroke="#fff" strokeWidth="2.6" />
      <path d="M19.5 19.5 24 24" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M11.8 14.5h5.4M14.5 11.8v5.4" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 rounded-lg font-semibold tracking-tight">
      <LogoMark />
      <span className="text-[15px]">Lectura</span>
    </Link>
  );
}
