import { Link } from "react-router-dom";
import CountryFlag from "./CountryFlag";

/** A player name that opens the player page when the player id is known (plain text otherwise), optionally with the national flag. */
export default function PlayerLink({ id, name, country, size = 18, className = "" }: { id?: number | string | null; name: string; country?: string | null; size?: number; className?: string }) {
  const body = <>{country ? <CountryFlag country={country} size={size} /> : null}<span>{name}</span></>;
  if (id === null || id === undefined || id === "") return <span className={`inline-flex items-center gap-2 ${className}`}>{body}</span>;
  return <Link to={`/player/${id}`} onClick={(e) => e.stopPropagation()} className={`inline-flex items-center gap-2 font-semibold underline-offset-2 hover:underline ${className}`} style={{ color: "inherit" }} title={`Open ${name}'s player page`}>{body}</Link>;
}
