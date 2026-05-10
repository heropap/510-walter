export interface Textbook {
  id: string;
  title: string;
  filename: string;
  status: string;
  total_chars: number;
  chapter_count: number;
  chapters?: Chapter[];
}

export interface Chapter {
  id: string;
  title: string;
  level: number;
  parent_id?: string | null;
  char_count: number;
  sort_order: number;
}

export interface GraphNode {
  id: string;
  name: string;
  definition: string;
  category: string;
  body_system: string;
  organ: string;
  anatomical_region: string;
  scale_level: string;
  stage: string;
  importance: string;
  frequency: number;
  evidence: string;
  source_textbooks: string[];
  confidence: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation_type: string;
  medical_relation_type: string;
  description: string;
  confidence: number;
  evidence: string;
}

export interface KnowledgeGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: Record<string, unknown>;
}

export interface Decision {
  id: string;
  action: string;
  affected_nodes: string[];
  result_node?: string | null;
  reason: string;
  confidence: number;
  char_saved: number;
  status: string;
  created_at: string;
}

export interface RagResponse {
  answer: string;
  citations: Array<Record<string, unknown>>;
  conversation_id?: string | null;
  provider: string;
}

export interface ConfigStatus {
  deepseek: {
    configured: boolean;
    client_available: boolean;
    model: string;
    base_url?: string | null;
  };
  dify: {
    chat_configured: boolean;
    knowledge_configured: boolean;
    base_url_configured: boolean;
    dataset_configured: boolean;
  };
  data: {
    textbooks: number;
    stats: Record<string, number | boolean>;
  };
}

