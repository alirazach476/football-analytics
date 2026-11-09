export const BODIES = [
  { id: "fifa", name: "FIFA", logo: "/logos/fifa.png" },
  { id: "uefa", name: "UEFA", logo: "/logos/uefa.png" },
  { id: "conmebol", name: "CONMEBOL", logo: "/logos/conmebol.png" },
] as const;
export const BODY_OF: Record<string, (typeof BODIES)[number][]> = { WC: [BODIES[0]], EURO: [BODIES[1]], UNL: [BODIES[1]], COPA: [BODIES[2]], FIN: [BODIES[1], BODIES[2]] };

/** The three governing bodies, shown as the site's main logos (on a light plate so every logo stays readable on any theme). */
export function BrandLogos({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <div className={"flex items-center gap-2 " + className} aria-label="FIFA, UEFA and CONMEBOL">
      {BODIES.map((b) => (
        <span key={b.id} className="grid place-items-center rounded-lg bg-white p-1 shadow-sm" style={{ height: size, minWidth: size }}>
          <img src={b.logo} alt={`${b.name} logo`} style={{ height: size - 8, width: "auto", maxWidth: size * 1.9 }} className="object-contain" />
        </span>
      ))}
    </div>
  );
}
