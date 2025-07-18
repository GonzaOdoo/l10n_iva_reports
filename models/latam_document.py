from odoo import api, models, fields, _
import logging

class LatamDocument(models.Model):
    _inherit = 'l10n_latam.document.type'

    rg90_code = fields.Char('Codigo RG90')