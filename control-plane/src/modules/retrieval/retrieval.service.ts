import { Injectable } from '@nestjs/common';
import { GraphService } from '../../db/graph.service';
import { PostgresService } from '../../db/postgres.service';
import { loadConfig } from '../../core/config';
import { RetrievalBundle } from '../../core/types';

@Injectable()
export class RetrievalService {
  private readonly cfg = loadConfig();

  constructor(
    private readonly postgres: PostgresService,
    private readonly graph: GraphService,
  ) {}

  async retrieve(claimType: string, jurisdiction = 'EW'): Promise<RetrievalBundle> {
    const rules = await this.fetchRules(claimType);
    let graphBundle = await this.graph.getClaimSubgraph(claimType, jurisdiction);

    if (graphBundle.nodes.length === 0) {
      graphBundle = await this.fetchGraphViaHttp(claimType, jurisdiction);
    }

    return { rules, graph: graphBundle };
  }

  private async fetchRules(claimType: string): Promise<Array<Record<string, unknown>>> {
    const rows = await this.postgres.query<Record<string, unknown>>(
      `
      SELECT rule_key, claim_type, jurisdiction, value_numeric, value_text,
             unit, description, authority_type, authority_ref, authority_url,
             effective_from, effective_to, is_prospective
      FROM rules
      WHERE claim_type = $1
         OR rule_key ILIKE $2
      ORDER BY effective_from DESC NULLS LAST
      LIMIT 25
      `,
      [claimType, `%${claimType}%`],
    );
    return rows;
  }

  private async fetchGraphViaHttp(
    claimType: string,
    jurisdiction: string,
  ): Promise<RetrievalBundle['graph']> {
    try {
      const url = new URL('/api/rag/graph', this.cfg.GRAPH_RAG_SERVICE_URL);
      url.searchParams.set('claim_type', claimType);
      url.searchParams.set('jurisdiction', jurisdiction);
      const res = await fetch(url.toString(), { signal: AbortSignal.timeout(5000) });
      if (!res.ok) {
        return { nodes: [], edges: [], source: 'graph_http_unavailable' };
      }
      const body = (await res.json()) as {
        nodes?: RetrievalBundle['graph']['nodes'];
        edges?: RetrievalBundle['graph']['edges'];
      };
      return {
        nodes: body.nodes ?? [],
        edges: body.edges ?? [],
        source: 'graph_rag_service_8018',
      };
    } catch {
      return { nodes: [], edges: [], source: 'graph_http_error' };
    }
  }
}
