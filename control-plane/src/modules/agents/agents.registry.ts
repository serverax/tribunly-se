export type AgentDescriptor = {
  name: string;
  domain: string;
  claimTypes: string[];
};

const REGISTRY: AgentDescriptor[] = [
  { name: 'deadline_agent', domain: 'employment', claimTypes: ['unfair_dismissal', 'discrimination'] },
  { name: 'evidence_agent', domain: 'employment', claimTypes: ['unfair_dismissal', 'wrongful_dismissal'] },
  { name: 'remedy_agent', domain: 'employment', claimTypes: ['unfair_dismissal', 'unpaid_wages'] },
  { name: 'acas_agent', domain: 'employment', claimTypes: ['unfair_dismissal'] },
];

export class AgentsRegistry {
  list(): AgentDescriptor[] {
    return [...REGISTRY];
  }

  forClaim(claimType: string): AgentDescriptor[] {
    return REGISTRY.filter((a) => a.claimTypes.includes(claimType));
  }
}

export const agentsRegistry = new AgentsRegistry();
