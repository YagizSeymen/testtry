// Agent registry — canonical names + icons. Reused across the UI wherever
// an AI-generated artifact needs to disclose which agent produced it.
import {
  ScanText,
  Filter,
  Gavel,
  FileText,
  Search,
  Swords,
  type LucideIcon,
} from "lucide-react";

export type AgentName =
  | "Extractor Agent"
  | "Screening Agent"
  | "Diligence Judge"
  | "Diligence Judge (re-verifying)"
  | "Memo Agent"
  | "Query Agent"
  | "Adversary Agent";

export const AGENT_ICON: Record<AgentName, LucideIcon> = {
  "Extractor Agent": ScanText,
  "Screening Agent": Filter,
  "Diligence Judge": Gavel,
  "Diligence Judge (re-verifying)": Gavel,
  "Memo Agent": FileText,
  "Query Agent": Search,
  "Adversary Agent": Swords,
};
