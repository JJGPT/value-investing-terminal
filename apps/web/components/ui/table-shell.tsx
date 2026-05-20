type TableShellProps = {
  columns: string[];
  rows: string[][];
};

export function TableShell({ columns, rows }: TableShellProps) {
  return (
    <div className="border-line overflow-hidden border">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <thead className="bg-graphite2 text-muted font-mono text-[11px] uppercase">
            <tr>
              {columns.map((column) => (
                <th key={column} className="border-line border-b px-4 py-3">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-line divide-y">
            {rows.map((row, rowIndex) => (
              <tr key={`row-${rowIndex}`} className="bg-panel/60">
                {row.map((cell, cellIndex) => (
                  <td
                    key={`cell-${rowIndex}-${cellIndex}`}
                    className="text-ink px-4 py-3"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
