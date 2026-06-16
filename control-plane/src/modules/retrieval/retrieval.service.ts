import { Injectable } from '@nestjs/common';
import { GraphService } from '../../db/graph.service';
import { PostgresService } from '../../db/postgres.service';
import { loadConfig } from '../../core/config';
import { RetrievalBundle } from '../../core/types';
import { GraphRagService } from '../graph-rag/graph-rag.service';

export interface HybridRetrievalContext {
  semantic: Array<Record<string, unknown>>;
  graph: RetrievalBundle['graph'] & { context_text?: string; engine?: string };
  rules: Array<Record<string, unknown>>;
}

@Injectable()
export class RetrievalService {
  private readonly cfg = loadConfig();

  constructor(
    private readonly postgres: PostgresService,
    private readonly graph: GraphService,
    private readonly graphRag: GraphRagService,
  ) {}

  async retrieve(claimType: string, jurisdiction = 'EW'): Promise<RetrievalBundle> {
    const hybrid = await this.retrieveHybrid(claimType, jurisdiction);
    return { rules: hybrid.rules, graph: hybrid.graph };
  }

  /** Hybrid merge: semantic (rules table) + graph (8018) + rules spine. */
  async retrieveHybrid(
    claimType: string,
    jurisdiction = 'EW',
    query?: string,
  ): Promise<HybridRetrievalContext> {
    const rules = await this.fetchRules(claimType);
    let graphBundle = await this.graph.getClaimSubgraph(claimType, jurisdiction);

    if (query && query.trim().length > 0) {
      const search = await this.graphRag.searchGraph(query, jurisdiction);
      graphBundle = {
        nodes: search.path as RetrievalBundle['graph']['nodes'],
        edges: search.edges as RetrievalBundle['graph']['edges'],
        source: search.engine,
        context_text: search.formatted,
        engine: search.engine,
      };
    } else if (graphBundle.nodes.length === 0) {
      const chain = await this.graphRag.buildLegalChain(claimType, jurisdiction);
      graphBundle = {
        nodes: chain.path as RetrievalBundle['graph']['nodes'],
        edges: chain.edges as RetrievalBundle['graph']['edges'],
        source: chain.engine,
        context_text: chain.formatted,
        engine: chain.engine,
      };
    }

    return {
      semantic: rules,
      graph: graphBundle,
      rules,
    };
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
}
