import { TerminalShell } from "../../components/shell/terminal-shell";
import { PlaceholderCard } from "../../components/ui/placeholder-card";
import { StatusList } from "../../components/ui/status-list";

export default function ResearchPage() {
  return (
    <TerminalShell
      eyebrow="Research"
      title="Analyst research workspace."
      description="A notebook foundation for future source-backed notes, evidence packets, memos, and reviewed workflows."
    >
      <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <PlaceholderCard
          label="Notebook"
          title="Research sections"
          description="The notebook shell is ready for structured investment research artifacts."
        >
          <StatusList
            items={[
              { label: "Thesis", status: "planned" },
              { label: "Business quality", status: "planned" },
              { label: "Risks", status: "planned" },
              { label: "Open questions", status: "planned" },
            ]}
          />
        </PlaceholderCard>

        <PlaceholderCard
          label="Evidence"
          title="Source-backed research area"
          description="Future evidence packets will cite filings, curated knowledge, and analyst notes. AI/RAG remains intentionally disabled."
        >
          <StatusList
            items={[
              { label: "Knowledge base", status: "offline" },
              { label: "Document retrieval", status: "offline" },
              { label: "Agent review", status: "offline" },
            ]}
          />
        </PlaceholderCard>
      </section>
    </TerminalShell>
  );
}
