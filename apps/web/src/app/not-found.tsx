import Link from "next/link";
export default function NotFound() {
  return (
    <div className="unavailable">
      <div className="eyebrow">404 · PAGE NOT FOUND</div>
      <h1>This investigation path does not exist</h1>
      <Link href="/incidents" className="button primary">
        Open incident queue
      </Link>
    </div>
  );
}
