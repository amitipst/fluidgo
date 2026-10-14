import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'

export default function DeleteRequestDialog({ contact, onClose }: { contact: { id: string; name: string }; onClose: () => void }) {
  const qc = useQueryClient()
  const [reason, setReason] = useState('')
  const send = useMutation({
    mutationFn: () => api.post(`/contacts/${contact.id}/delete-request`, { reason: reason.trim() }).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['contacts'] }); qc.invalidateQueries({ queryKey: ['contact-requests'] }); qc.invalidateQueries({ queryKey: ['account'] }); toast.success('Deletion requested — awaiting approval.'); onClose() },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl p-5 w-full max-w-md space-y-3" onClick={e => e.stopPropagation()}>
        <h3 className="font-bold">Request deletion of {contact.name}</h3>
        <p className="text-xs text-wep-muted">Needs your reporting manager and one of governance / inside sales to approve. If the person simply left the company, use “Mark as left” instead.</p>
        <textarea className="form-input w-full" rows={3} placeholder="Reason (min 5 characters)" value={reason} onChange={e => setReason(e.target.value)} />
        <div className="flex justify-end gap-2">
          <button className="btn-outline text-sm" onClick={onClose}>Cancel</button>
          <button className="btn-primary text-sm disabled:opacity-40" disabled={reason.trim().length < 5 || send.isPending} onClick={() => send.mutate()}>Send request</button>
        </div>
      </div>
    </div>
  )
}
