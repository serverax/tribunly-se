import { Injectable, Logger } from '@nestjs/common';
import { loadConfig } from '../../core/config';

export interface LegalChainNode {
  node_id: string;
  node_type: string;
  label: string;
  description?: string;
  authority_level?: number;
  source_ref?: string;
  source_url?: string;
}

export interface LegalChainResult {
  claim_type: string;
  path: LegalChainNode[];
  edges: Array<Record<string, unknown>>;
  confidence: number;
  engine: string;
  context_text?: string;
  formatted?: string;
  path_score?: number;
}

@Injectable()
export class GraphRagService {
  private readonly logger = new Logger(GraphRagService.name);
  private readonly cfg = loadConfig();

  /**
   * Build legal authority chain via Python graph-rag service (8018).
   * Neo4j when NEO4J_ENABLED=true; Postgres fallback inside that service.
   */
  async buildLegalChain(
    claimType: string,
    jurisdiction = 'EW',
    module = claimType,
  ): Promise<LegalChainResult> {
    const base = this.cfg.GRAPH_RAG_SERVICE_URL.replace(/\/$/, '');
    const res = await fetch(`${base}/api/graphrag/traverse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        claim_type: claimType,
        module,
        jurisdiction,
        facts: {},
      }),
      signal: AbortSignal.timeout(15_000),
    });

    if (!res.ok) {
      const text = await res.text();
      this.logger.warn(`Graph traverse failed: ${res.status} ${text.slice(0, 200)}`);
      return {
        claim_type: claimType,
        path: [],
        edges: [],
        confidence: 0,
        engine: 'fail_closed',
      };
    }

    const body = (await res.json()) as LegalChainResult & { missing_prerequisites?: string[] };
    const chain: LegalChainResult = {
      claim_type: body.claim_type ?? claimType,
      path: body.path ?? [],
      edges: body.edges ?? [],
      confidence: body.confidence ?? 0,
      engine: (body as { engine?: string }).engine ?? 'postgres',
    };
    chain.formatted = this.format(chain);
    chain.path_score = this.scorePath(chain);
    return chain;
  }

  async searchGraph(query: string, jurisdiction = 'EW', limit = 10): Promise<LegalChainResult & { query: string }> {
    const base = this.cfg.GRAPH_RAG_SERVICE_URL.replace(/\/$/, '');
    const res = await fetch(`${base}/api/graph/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, jurisdiction, limit }),
      signal: AbortSignal.timeout(15_000),
    });

    if (!res.ok) {
      return {
        query,
        claim_type: '',
        path: [],
        edges: [],
        confidence: 0,
        engine: 'fail_closed',
      };
    }

    const body = (await res.json()) as LegalChainResult & { query: string; matches?: LegalChainNode[] };
    const path = body.path ?? body.matches ?? [];
    const chain: LegalChainResult & { query: string } = {
      query,
      claim_type: body.claim_type ?? '',
      path,
      edges: body.edges ?? [],
      confidence: body.confidence ?? 0,
      engine: body.engine ?? 'postgres',
    };
    chain.formatted = this.format(chain);
    chain.path_score = this.scorePath(chain);
    return chain;
  }

  format(chain: LegalChainResult): string {
    const lines = [`[Graph engine=${chain.engine} confidence=${chain.confidence.toFixed(2)}]`];
    lines.push('LEGAL GRAPH CHAIN:');
    for (const node of chain.path ?? []) {
      const ref = node.source_ref ? ` (${node.source_ref})` : '';
      lines.push(`  [${node.node_type}] ${node.label}${ref}`);
    }
    return lines.join('\n');
  }

  scorePath(chain: LegalChainResult): number {
    const base = chain.confidence ?? 0;
    const tests = (chain.path ?? []).filter((n) => n.node_type === 'legal_test').length;
    const sourced = (chain.path ?? []).filter((n) => n.source_url).length;
    return Math.min(1, base + Math.min(0.2, tests * 0.05) + sourced * 0.02);
  }
}
