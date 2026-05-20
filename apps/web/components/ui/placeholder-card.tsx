import type { ReactNode } from "react";

type PlaceholderCardProps = {
  label: string;
  title: string;
  description: string;
  children?: ReactNode;
};

export function PlaceholderCard({
  label,
  title,
  description,
  children
}: PlaceholderCardProps) {
  return (
    <section className="border-line bg-panel/85 border p-5">
      <p className="text-muted font-mono text-[11px] uppercase">{label}</p>
      <h2 className="text-ink mt-3 text-lg font-semibold">{title}</h2>
      <p className="text-muted mt-2 text-sm leading-6">{description}</p>
      {children ? <div className="mt-5">{children}</div> : null}
    </section>
  );
}
