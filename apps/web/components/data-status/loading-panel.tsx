type LoadingPanelProps = {
  label: string;
};

export function LoadingPanel({ label }: LoadingPanelProps) {
  return (
    <div className="border-line bg-panel/85 border p-5">
      <p className="text-muted font-mono text-[11px] uppercase">{label}</p>
      <div className="mt-5 space-y-3">
        <div className="bg-line h-3 w-2/3" />
        <div className="bg-line h-3 w-full" />
        <div className="bg-line h-3 w-1/2" />
      </div>
    </div>
  );
}
