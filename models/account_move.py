from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)
class AccountMove(models.Model):
    _inherit = 'account.move'

    timbrado_proveedor = fields.Char('Timbrado Proveedor')
    form_145 = fields.Selection(selection=[('original','Original'),('rect','Rectificativa')],string ='Formulario 145', default = 'original')


