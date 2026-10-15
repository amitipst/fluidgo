import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api, { getErrorMessage } from '@/hooks/useApi'
import { toast } from '@/store/toastStore'
import Modal from '@/components/ui/Modal'

export default function DeleteRequestDialog({ contact, onClose }: { contact: { id: string; name: string }; onClose: () => void }) {
  const qc = useQueryClient()
  const [reason, setReason] = useState('')
  const send = useMutation({
    mutationFn: () => api.post(`/contacts/${contact.id}/delete-request`, { reason: reason.trim() }).then(r => r.data),
    onSuccess: () => { ;['contacts', 'contact-requests', 'account'].forEach(k => qc.invalidateQueries({ queryKey: [k] })); toast.success('Deletion requested — awaiting approval.'); onClose() },
    onError: (e: any) => toast.error(getErrorMessage(e)),
  })
  return (
    <Modal title={`Request deletion of ${contact.name}`} subtitle="Needs your reporting manager and one of governance / inside sales to approve." onClose={onClose} size="sm">
      <p className="text-xs text-wep-muted">If this person simply left the company, use <b>Mark as left</b> instead — it keeps their history.</p>
      <div>
        <label htmlFor="del-reason" className="form-label block mb-1">Reason <span className="text-brand-pink" aria-hidden>*</span></label>
        <textarea id="del-reason" className="form-input" rows={3} autoFocus placeholder="Why should this contact be deleted? (min 5 characters)" value={reason} onChange={e => setReason(e.target.value)} />
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-outline" onClick={onClose}>Cancel</button>
        <button type="button" className="btn-danger disabled:opacity-50" disabled={reason.trim().length < 5 || send.isPending} onClick={() => send.mutate()}>Send request</button>
      </div>
    </Modal>
  )
}
