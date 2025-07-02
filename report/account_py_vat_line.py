# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools
from odoo.tools import SQL


class AccountPyVatLine(models.Model):
    """ Base model for new Argentine VAT reports. The idea is that these lines have all the necessary data and which any
    changes in odoo, this ones will be taken for this cube and then no changes will be needed in the reports that use
    this lines. A line is created for each accounting entry that is affected by VAT tax.

    Basically which it does is covert the accounting entries into columns depending on the information of the taxes and
    add some other fields """

    _name = "account.py.vat.line"
    _description = "Linea de Iva para reporte Paraguay (Localizacion Xmarts)"
    _rec_name = 'move_name'
    _auto = False
    _order = 'invoice_date asc, move_name asc, id asc'

    document_type_id = fields.Many2one('l10n_latam.document.type', 'Document Type', readonly=True)
    date = fields.Date(readonly=True)
    invoice_date = fields.Date(readonly=True)
    ruc = fields.Char(readonly=True)
    l10n_latam_document_type_id = fields.Char(readonly=True)
    partner_name = fields.Char(readonly=True)
    move_name = fields.Char(readonly=True)
    move_type = fields.Selection(selection=[
            ('entry', 'Journal Entry'),
            ('out_invoice', 'Customer Invoice'),
            ('out_refund', 'Customer Credit Note'),
            ('in_invoice', 'Vendor Bill'),
            ('in_refund', 'Vendor Credit Note'),
            ('out_receipt', 'Sales Receipt'),
            ('in_receipt', 'Purchase Receipt'),
        ], readonly=True)
    
    base_10 = fields.Monetary(readonly=True, string='Grav. 10,5%', currency_field='company_currency_id')
    #Deberia buscar los impuestos por el campo l10n_xma_tax_factor_type_id.code == 1 en account.tax y usar amount para definir si es 5 o 10
    vat_10 = fields.Monetary(readonly=True, string='VAT 10,5%', currency_field='company_currency_id')
    base_5 = fields.Monetary(readonly=True, string='Grav. 5%', currency_field='company_currency_id')
    vat_5 = fields.Monetary(readonly=True, string='VAT 5%', currency_field='company_currency_id')
    not_taxed = fields.Monetary(
        readonly=True, string='Not taxed/ex', help=r'Not Taxed / Exempt.\All lines that have VAT 0, Exempt, Not Taxed'
        ' or Not Applicable', currency_field='company_currency_id')
    total = fields.Monetary(readonly=True, currency_field='company_currency_id')
    state = fields.Selection([('draft', 'Unposted'), ('posted', 'Posted')], 'Status', readonly=True)
    journal_id = fields.Many2one('account.journal', 'Journal', readonly=True, auto_join=True)
    partner_id = fields.Many2one('res.partner', 'Partner', readonly=True, auto_join=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True, auto_join=True)
    company_currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    move_id = fields.Many2one('account.move', string='Entry', auto_join=True, index='btree_not_null')
    timbrado = fields.Char('Timbrado') #l10n_xma_number_timbrado_asociado en account.move

    def open_journal_entry(self):
        self.ensure_one()
        return self.move_id.get_formview_action()

    def init(self):
        cr = self._cr
        tools.drop_view_if_exists(cr, self._table)
        query = self._py_vat_line_build_query()
        sql = SQL("""CREATE or REPLACE VIEW account_py_vat_line as (%s)""", query)
        cr.execute(sql)

    @property
    def _table_query(self):
        return self._ar_vat_line_build_query()

    @api.model
    def _py_vat_line_build_query(self, table_references=None, search_condition=None,
                                column_group_key='', tax_types=('sale', 'purchase')) -> SQL:
        """Construye la consulta SQL para el reporte de IVA Paraguay"""
        if table_references is None:
            table_references = SQL('account_move_line')
        search_condition = SQL('AND (%s)', search_condition) if search_condition else SQL()

        query = SQL(
            """
            SELECT
                %(column_group_key)s AS column_group_key,
                account_move.id,
                rp.vat AS ruc,
                ldt.name AS l10n_latam_document_type_id,
                rp.name AS partner_name,
                COALESCE(nt.type_tax_use, bt.type_tax_use) AS tax_type,
                account_move.id AS move_id,
                account_move.move_type,
                account_move.date,
                account_move.invoice_date,
                account_move.partner_id,
                account_move.journal_id,
                account_move.name AS move_name,
                account_move.l10n_latam_document_type_id as document_type_id,
                account_move.state,
                account_move.company_id,
                account_move.l10n_xma_number_timbrado_asociado AS timbrado,
                -- Campos para IVA 10%
                SUM(CASE WHEN bt.l10n_xma_tax_factor_type_id = 1 AND bt.amount = 10 THEN account_move_line.balance ELSE 0 END) AS base_10,
                SUM(CASE WHEN nt.l10n_xma_tax_factor_type_id = 1 AND nt.amount = 10 THEN account_move_line.balance ELSE 0 END) AS vat_10,
                -- Campos para IVA 5%
                SUM(CASE WHEN bt.l10n_xma_tax_factor_type_id = 1 AND bt.amount = 5 THEN account_move_line.balance ELSE 0 END) AS base_5,
                SUM(CASE WHEN nt.l10n_xma_tax_factor_type_id = 1 AND nt.amount = 5 THEN account_move_line.balance ELSE 0 END) AS vat_5,
                -- No gravados/exentos
                SUM(CASE WHEN bt.l10n_xma_tax_factor_type_id != 1 OR bt.l10n_xma_tax_factor_type_id IS NULL THEN account_move_line.balance ELSE 0 END) AS not_taxed,
                -- Total
                SUM(account_move_line.balance) AS total
            FROM
                %(table_references)s
                JOIN account_move ON account_move_line.move_id = account_move.id
                LEFT JOIN account_tax AS nt ON account_move_line.tax_line_id = nt.id
                LEFT JOIN account_move_line_account_tax_rel AS amltr ON account_move_line.id = amltr.account_move_line_id
                LEFT JOIN account_tax AS bt ON amltr.account_tax_id = bt.id
                LEFT JOIN res_partner AS rp ON rp.id = account_move.commercial_partner_id
                LEFT JOIN l10n_latam_document_type AS ldt ON account_move.l10n_latam_document_type_id = ldt.id
            WHERE
                (account_move_line.tax_line_id IS NOT NULL OR bt.l10n_xma_tax_factor_type_id IS NOT NULL)
                AND (nt.type_tax_use IN %(tax_types)s OR bt.type_tax_use IN %(tax_types)s)
                %(search_condition)s
            GROUP BY
                account_move.id, rp.id, ldt.id, COALESCE(nt.type_tax_use, bt.type_tax_use)
            ORDER BY
                account_move.invoice_date, account_move.name
            """,
            column_group_key=column_group_key,
            table_references=table_references,
            tax_types=tax_types,
            search_condition=search_condition,
        )
        return query