// Matches backend app/services/export_guard.py: bulk downloads are for managers and above.
// Reps, inside sales and pre-sales cannot download; governance has no financial downloads.
const NO_EXPORT_ROLES = ['rep', 'inside_sales', 'pre_sales', 'governance']
export const canExport = (role?: string | null) => !!role && !NO_EXPORT_ROLES.includes(role)
