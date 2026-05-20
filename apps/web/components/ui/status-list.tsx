type StatusListProps = {
  items: Array<{
    label: string;
    status: string;
  }>;
};

export function StatusList({ items }: StatusListProps) {
  return (
    <div className="border-line divide-line divide-y border">
      {items.map((item) => (
        <div
          key={item.label}
          className="flex items-start justify-between gap-4 px-4 py-3"
        >
          <span className="text-ink min-w-0 break-words text-sm">
            {item.label}
          </span>
          <span className="text-muted max-w-[65%] break-words text-right font-mono text-[11px] uppercase">
            {item.status}
          </span>
        </div>
      ))}
    </div>
  );
}
