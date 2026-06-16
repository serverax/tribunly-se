import { Injectable, Logger } from '@nestjs/common';
import { randomUUID } from 'crypto';
import { ProcessRequest, ProcessResponse } from '../../core/types';
import { detectLanguage, assessProxyHeaders } from '../../core/mother_algorithm/language_router';
import { GovernanceService } from '../governance/governance.service';
import { MemoryService } from '../memory/memory.service';
import { ReasoningService } from '../reasoning/reasoning.service';
import { RetrievalService } from '../retrieval/retrieval.service';
import { agentsRegistry } from '../agents/agents.registry';

@Injectable()
export class OrchestratorService {
  private readonly logger = new Logger(OrchestratorService.name);

  constructor(
    private readonly retrieval: RetrievalService,
    private readonly reasoning: ReasoningService,
    private readonly governance: GovernanceService,
    private readonly memory: MemoryService,
  ) {}

  async process(request: ProcessRequest): Promise<ProcessResponse> {
    const traceId = randomUUID();
    this.logger.log(`process start trace=${traceId} claim=${request.claim_type}`);

    const agents = agentsRegistry.forClaim(request.claim_type);
    this.logger.debug(`agents selected: ${agents.map((a) => a.name).join(', ') || 'none'}`);

    const retrieval = await this.retrieval.retrieve(
      request.claim_type,
      request.jurisdiction ?? 'EW',
    );

    const locale = detectLanguage({
      preferredLanguage: (request as ProcessRequest & { language?: string }).language,
      text: request.query,
    });

    const brainRaw = await this.reasoning.assess(request, {
      language: locale,
      headers: assessProxyHeaders(locale),
    });
    const governance = this.governance.validateAssessment(brainRaw);

    const response = this.governance.buildProcessResponse(retrieval, governance, traceId);
    await this.memory.rememberProcess(traceId, JSON.stringify(response));
    return response;
  }
}
