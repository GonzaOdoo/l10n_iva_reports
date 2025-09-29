from odoo import api, models, fields, _
import re
import logging

_logger = logging.getLogger(__name__)
class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_xma_indentification_type = fields.Selection(
        selection_add = [('11','RUC')]
    )

    def check_vat_py(self, vat):
        return vat.isdigit() and len(vat) == 8

    #l10n_xma_indentification_type = fields.Selection(
        #selection = [('11','RUC'),('12','Cédula de identidad'),('13','Pasaporte'),('14','Cédula extranjero'),('15','Sin nombre'),('16','Diplomático'),('17','Identificación Tributaria')], string='Tipo de identificación',default='11')