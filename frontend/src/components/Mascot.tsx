import { motion } from "framer-motion";

// Mascot artwork lives in /public/mascots/<theme key>.<ext>. Editions without a mascot (e.g. the cancelled Finalissima 2026) have none.
const MASCOTS = new Set("wc-1998 wc-2002 wc-2006 wc-2010 wc-2014 wc-2018 wc-2022 wc-2026 wc-2030 euro-2000 euro-2004 euro-2008 euro-2012 euro-2016 euro-2020 euro-2024 euro-2028 copa-2001 copa-2004 copa-2007 copa-2011 copa-2015 copa-2016 copa-2019 copa-2021 copa-2024 copa-2028 fin-2022 unl".split(" "));
export const mascotUrl = (key: string) => (MASCOTS.has(key) ? `/mascots/${key}.${key === "wc-2010" ? "svg" : "webp"}` : null);

export default function Mascot({ themeKey, name }: { themeKey: string; name: string }) {
  const src = mascotUrl(themeKey);
  if (!src) return null;
  return (
    <motion.figure initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.6 }} className="relative m-0 flex h-52 w-40 items-center justify-center rounded-3xl bg-white/95 p-3 shadow-2xl sm:h-60 sm:w-48">
      <img src={src} alt={`${name} mascot`} className="h-full w-full object-contain" loading="lazy" />
    </motion.figure>
  );
}
