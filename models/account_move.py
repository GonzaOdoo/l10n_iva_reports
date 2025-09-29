from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)
class AccountMove(models.Model):
    _inherit = 'account.move'

    timbrado_proveedor = fields.Char('Timbrado Proveedor')
    form_145 = fields.Selection(selection=[('original','Original'),('rect','Rectificativa')],string ='Formulario 145', default = 'original')

    @api.constrains('timbrado_proveedor')
    def _check_timbrado_proveedor(self):
        for rec in self:
            if rec.timbrado_proveedor:
                # Eliminar espacios u otros caracteres invisibles (opcional, pero recomendado)
                valor = rec.timbrado_proveedor.strip()
                if len(valor) != 8 or not valor.isdigit():
                    raise ValidationError(
                        "El Timbrado Proveedor debe tener exactamente 8 dígitos numéricos."
                    )
                # Opcional: asegurar que el campo quede limpio (sin espacios)
                if valor != rec.timbrado_proveedor:
                    rec.timbrado_proveedor = valor
