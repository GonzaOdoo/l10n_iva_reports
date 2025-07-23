from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)
class AccountPayment(models.Model):
    _inherit = 'account.payment'

    secuencia = fields.Char('Secuencia')

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        for payment in payments:
            if payment.state in ['paid','in_process']:
                for invoice in payment.invoice_ids:
                    _logger.info(invoice)
                    if invoice.l10n_xma_payment_term == 'credit':
                        if not payment.secuencia:
                            if payment.payment_type == 'inbound' and payment.partner_type == 'customer':
                                # Pago de cliente - usar secuencia de recibo de pagos
                                sequence = env['ir.sequence'].next_by_code('recibo_pago')
                                payment.write({'secuencia': sequence})
                                _logger.info("Secuencia de recibo de pago asignada: %s", sequence)
                                
                            elif payment.payment_type == 'outbound' and payment.partner_type == 'supplier':
                                # Pago de proveedor - usar secuencia de reporte de pagos
                                sequence = env['ir.sequence'].next_by_code('reporte_pago')
                                payment.write({'secuencia': sequence})
                                _logger.info("Secuencia de reporte de pago asignada: %s", sequence)
        return payments