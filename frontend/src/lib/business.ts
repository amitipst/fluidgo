// Business-line labels. Canonical source: backend/app/models/__init__.py's
// User.business column comment (fluidpro | fluidprint | floxtax | hooks).
// Team.tsx and Dashboard.tsx each keep their own local copy of this same
// map today — left as-is to limit the size of this change; worth folding
// into this shared file on a future pass (not urgent: these are static
// labels, not logic, so the duplication carries low risk of drifting).
export const BUSINESS_LABEL: Record<string, string> = {
  fluidpro: 'fluidPro (IT Infra)', fluidprint: 'fluidPrint (Managed Print)',
  floxtax: 'floxtax (GST/ASP)', hooks: 'Hooks (POS/Channel)',
}
