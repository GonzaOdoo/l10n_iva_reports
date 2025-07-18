from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)
class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_xma_indentification_type = fields.Selection(
        selection_add = [('11','RUC')]
    )


    #l10n_xma_indentification_type = fields.Selection(
        #selection = [('11','RUC'),('12','Cédula de identidad'),('13','Pasaporte'),('14','Cédula extranjero'),('15','Sin nombre'),('16','Diplomático'),('17','Identificación Tributaria')], string='Tipo de identificación',default='11')