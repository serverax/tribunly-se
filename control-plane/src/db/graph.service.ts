import { Injectable, Logger } from '@nestjs/common';
import { loadConfig } from '../core/config';
import { GraphEdge, GraphNode } from '../core/types';
import { PostgresService } from './postgres.service';

const CLAIM_ROOT_NODES: Record<string, string> = {
  unfair_dismissal: 'ud_claim',
  unpaid_wages: 'upw_claim',
  wrongful_dismissal: 'ud_claim',
};

/**
 * Postgres-first graph adapter (owner decision Q2).
 * Neo4j is optional behind NEO4J_ENABLED=true for future experiments only.
 */
@Injectable()
export class GraphService {
  private readonly logger = new Logger(GraphService.name);
  private readonly cfg = loadConfig();

  constructor(private readonly postgres: PostgresService) {}

  async getClaimSubgraph(
    claimType: string,
    jurisdiction = 'EW',
    maxDepth = 2,
  ): Promise<{ nodes: GraphNode[]; edges: GraphEdge[]; source: string; context_text?: string; engine?: string }> {
    if (this.cfg.NEO4J_ENABLED) {
      this.logger.warn(
        'NEO4J_ENABLED=true but Neo4j driver is not bundled; falling back to Postgres legal_nodes/legal_edges',
      );
    }
    return this.postgresSubgraph(claimType, jurisdiction, maxDepth);
  }

  private async postgresSubgraph(
    claimType: string,
    jurisdiction: string,
    maxDepth: number,
  ): Promise<{ nodes: GraphNode[]; edges: GraphEdge[]; source: string }> {
    const root = CLAIM_ROOT_NODES[claimType];
    if (!root) {
      return { nodes: [], edges: [], source: 'postgres_graph_empty' };
    }

    const nodes = await this.postgres.query<GraphNode>(
      `
      WITH RECURSIVE walk AS (
        SELECT e.to_node_id AS node_id, 1 AS depth
        FROM legal_edges e
        WHERE e.from_node_id = $1
        UNION
        SELECT e.to_node_id, w.depth + 1
        FROM legal_edges e
        JOIN walk w ON e.from_node_id = w.node_id
        WHERE w.depth < $3
      )
      SELECT n.node_id, n.node_type, n.label, n.description,
             n.jurisdiction, n.authority_level
      FROM legal_nodes n
      WHERE n.is_active = true
        AND n.jurisdiction = $2
        AND (n.node_id = $1 OR n.node_id IN (SELECT node_id FROM walk))
      ORDER BY n.authority_level NULLS LAST, n.label
      LIMIT 50
      `,
      [root, jurisdiction, maxDepth],
    );

    const nodeIds = [root, ...nodes.map((n) => n.node_id)];
    const edges = await this.postgres.query<GraphEdge>(
      `
      SELECT from_node_id, to_node_id, relationship_type
      FROM legal_edges
      WHERE from_node_id = ANY($1::text[])
        AND to_node_id = ANY($1::text[])
      LIMIT 100
      `,
      [nodeIds],
    );

    const rootNode = await this.postgres.query<GraphNode>(
      `
      SELECT node_id, node_type, label, description, jurisdiction, authority_level
      FROM legal_nodes
      WHERE node_id = $1 AND jurisdiction = $2 AND is_active = true
      LIMIT 1
      `,
      [root, jurisdiction],
    );

    const mergedNodes = [...rootNode, ...nodes.filter((n) => n.node_id !== root)];
    return {
      nodes: mergedNodes,
      edges,
      source: 'postgres_legal_graph',
    };
  }
}
