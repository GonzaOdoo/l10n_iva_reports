# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools
from odoo.tools import SQL
import re
import logging

_logger = logging.getLogger(__name__)
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
    identification_type_id = fields.Char('Tipo de identificacion')
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
    l10n_xma_branch = fields.Char('Sucursal', readonly=True)
    l10n_xma_dispatch_point = fields.Char('Punto de Emisión', readonly=True)
    full_move_name = fields.Char('Documento Completo', readonly=True)
    payment_term = fields.Char('Terminos de pago')
    form_145 = fields.Char('Formulario 145')
    
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
        return self._py_vat_line_build_query()

    @api.model
    def _py_vat_line_build_query(self, table_references=None, search_condition=None,
                                column_group_key='', tax_types=('sale', 'purchase')) -> SQL:
        if table_references is None:
            table_references = SQL('account_move_line')
        if search_condition is not None:
            search_condition = SQL('AND (%s)', search_condition)
        else:
            search_condition = SQL()
        column_group_key = column_group_key or SQL("NULL")
        return SQL(
            """
            SELECT
                %(column_group_key)s AS column_group_key,
                account_move.id,
                rp.vat AS ruc,
                COALESCE(NULLIF(ldt.name ->> 'es_PY', ''), NULLIF(ldt.name ->> 'en_US', '')) AS l10n_latam_document_type_id,
                rp.name AS partner_name,
                COALESCE(nt.type_tax_use, bt.type_tax_use) AS tax_type,
                account_move.id AS move_id,
                account_move.move_type,
                account_move.date,
                account_move.invoice_date,
                account_move.partner_id,
                account_move.journal_id,
                account_move.name AS move_name,
                account_move.form_145 as form_145,
                -- Campos adicionales para el nombre completo del documento
                ldt.l10n_xma_branch,
                ldt.l10n_xma_dispatch_point,
                CASE
                    -- Para facturas de entrada o notas de crédito (compras)
                    WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN
                        COALESCE(NULLIF(account_move.ref, ''), account_move.name)
                
                    -- Para otros tipos (ventas, recibos, etc.)
                    ELSE
                        CONCAT_WS('-',
                            COALESCE(ldt.l10n_xma_branch, '001'),
                            COALESCE(ldt.l10n_xma_dispatch_point, '001'),
                            account_move.name
                        )
                END AS full_move_name,
                account_move.l10n_latam_document_type_id as document_type_id,
                account_move.state,
                account_move.company_id,
                CASE
                    WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN account_move.timbrado_proveedor
                    ELSE ldt.l10n_xma_authorization_code
                END AS timbrado,
                CASE
                    WHEN account_move.l10n_xma_payment_term = 'cash' THEN 'Contado'
                    WHEN account_move.l10n_xma_payment_term = 'credit' THEN 'Crédito'
                    ELSE account_move.l10n_xma_payment_term
                END AS payment_term,
        
                -- Impuestos...
                SUM(CASE WHEN bt.l10n_xma_tax_factor_type_id = 9 AND bt.amount = 10 THEN account_move_line.balance ELSE 0 END) AS base_10,
                SUM(CASE WHEN nt.l10n_xma_tax_factor_type_id = 9 AND nt.amount = 10 THEN account_move_line.balance ELSE 0 END) AS vat_10,
                SUM(CASE WHEN bt.l10n_xma_tax_factor_type_id = 9 AND bt.amount = 5 THEN account_move_line.balance ELSE 0 END) AS base_5,
                SUM(CASE WHEN nt.l10n_xma_tax_factor_type_id = 9 AND nt.amount = 5 THEN account_move_line.balance ELSE 0 END) AS vat_5,
                0 AS not_taxed,
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




class AccountPyVatCsvLine(models.Model):
    _name = "account.py.vat.csv.line"
    _description = "Línea de IVA Paraguay - Formato CSV oficial"
    _auto = False

    company_currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id, readonly=True)
    registro_codigo_tipo = fields.Char('Código Tipo de Registro', readonly=True)
    proveedor_tipo_documento = fields.Char('Tipo Documento', readonly=True)
    proveedor_numero_documento = fields.Char('Número Documento', readonly=True)
    proveedor_nombre = fields.Char('Nombre/Razón Social', readonly=True)
    tipo_comprobante_codigo = fields.Char('Código Comprobante', readonly=True)
    fecha_emision = fields.Date('Fecha Emisión', readonly=True)
    numero_timbrado = fields.Char('Timbrado', readonly=True)
    numero_comprobante = fields.Char('Número Comprobante', readonly=True)
    gravado_10 = fields.Monetary('Gravado 10%', currency_field='company_currency_id', readonly=True)
    gravado_5 = fields.Monetary('Gravado 5%', currency_field='company_currency_id', readonly=True)
    exento = fields.Monetary('Exento', currency_field='company_currency_id', readonly=True)
    total_comprobante = fields.Monetary('Total', currency_field='company_currency_id', readonly=True)
    condicion_compra_codigo = fields.Char('Condición de Compra', readonly=True)
    moneda_extranjera = fields.Char('Moneda Extranjera', readonly=True)
    imputa_iva = fields.Char('Imputa IVA', readonly=True)
    imputa_ire = fields.Char('Imputa IRE', readonly=True)
    imputa_irp_rsp = fields.Char('Imputa IRP-RSP', readonly=True)
    no_imputa = fields.Char('No Imputa', readonly=True)
    comprobante_venta_numero = fields.Char('Nro. Comprobante Venta', readonly=True)
    timbrado_venta = fields.Char('Timbrado Venta', readonly=True)

    def init(self):
        cr = self._cr
        tools.drop_view_if_exists(cr, self._table)
        query = self._py_vat_csv_line_build_query()
        sql = SQL("""CREATE or REPLACE VIEW account_py_vat_csv_line as (%s)""", query)
        cr.execute(sql)

    @property
    def _table_query(self):
        return self._py_vat_csv_line_build_query()
         
    @api.model
    def _py_vat_csv_line_build_query(self, table_references=None, search_condition=None,
                                column_group_key='', tax_types=('sale', 'purchase')) -> SQL:
        # Esta es tu nueva consulta SQL que genera los datos en el formato requerido
        if table_references is None:
            table_references = SQL('account_move_line')
        # Interceptamos y modificamos la search_condition si existe
        if search_condition and isinstance(search_condition, SQL):
            raw_sql = str(search_condition)
    
            # Buscamos y eliminamos cualquier parte que mencione l10n_latam_use_documents
            pattern = r'AND $$(?:"account_move_line"$$\."journal_id" IN $$SELECT[^)]*?"l10n_latam_use_documents"[^)]*?$$)'
            modified_sql = re.sub(pattern, '', raw_sql)
            _logger.info(modified_sql)
            # Reconstruimos como objeto SQL
            
        if search_condition is not None:
            search_condition = SQL('AND (%s)', search_condition)
        else:
            search_condition = SQL()
        
        column_group_key = column_group_key or SQL("NULL")
        return SQL("""
            SELECT
                %(column_group_key)s AS column_group_key,
                account_move.id,
                CASE
                    WHEN account_move.move_type IN ('out_invoice', 'out_refund') THEN '1'
                    WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN '2'
                    ELSE NULL
                END AS registro_codigo_tipo,
                CASE rp.l10n_xma_indentification_type
                    WHEN '1' THEN '12'
                    WHEN '2' THEN '13'
                    WHEN '3' THEN '14'
                    WHEN '4' THEN '15'
                    WHEN '11' THEN '11'
                    -- Agrega más mapeos según sea necesario
                    ELSE '99'  -- Valor por defecto si no coincide con ninguno
                END AS proveedor_tipo_documento,
                TRIM(SPLIT_PART(rp.vat, '-', 1)) AS proveedor_numero_documento,
                rp.name AS proveedor_nombre,
                ldt.rg90_code AS tipo_comprobante_codigo,
                account_move.invoice_date AS fecha_emision,
                CASE
                    WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN account_move.timbrado_proveedor
                    ELSE ldt.l10n_xma_authorization_code
                END AS numero_timbrado,
                CASE
                    -- Para facturas de entrada o notas de crédito (compras)
                    WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN
                        COALESCE(NULLIF(account_move.ref, ''), account_move.name)
                
                    -- Para otros tipos (ventas, recibos, etc.)
                    ELSE
                        CONCAT_WS('-',
                            COALESCE(ldt.l10n_xma_branch, '001'),
                            COALESCE(ldt.l10n_xma_dispatch_point, '001'),
                            account_move.name
                        )
                END AS numero_comprobante,
                CASE
                    WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN -1
                    ELSE 1
                END AS signo,
            
                -- Bases y montos de impuesto (con signo aplicado directamente)
                SUM(CASE WHEN bt.l10n_xma_tax_factor_type_id = 9 AND bt.amount = 10 THEN account_move_line.balance ELSE 0 END) *
                    (CASE WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN -1 ELSE 1 END)
                    AS base_10,
                
                SUM(CASE WHEN nt.l10n_xma_tax_factor_type_id = 9 AND nt.amount = 10 THEN account_move_line.balance ELSE 0 END) *
                    (CASE WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN -1 ELSE 1 END)
                    AS vat_10,
                
                SUM(CASE WHEN bt.l10n_xma_tax_factor_type_id = 9 AND bt.amount = 5 THEN account_move_line.balance ELSE 0 END) *
                    (CASE WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN -1 ELSE 1 END)
                    AS base_5,
                
                SUM(CASE WHEN nt.l10n_xma_tax_factor_type_id = 9 AND nt.amount = 5 THEN account_move_line.balance ELSE 0 END) *
                    (CASE WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN -1 ELSE 1 END)
                    AS vat_5,
                
                SUM(CASE WHEN bt.l10n_xma_tax_factor_type_id = 11 THEN account_move_line.balance ELSE 0 END) *
                    (CASE WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN 1 ELSE -1 END)
                    AS exento,
            
                (
                    SUM(CASE WHEN bt.l10n_xma_tax_factor_type_id = 9 AND bt.amount = 10 THEN account_move_line.balance ELSE 0 END) +
                    SUM(CASE WHEN nt.l10n_xma_tax_factor_type_id = 9 AND nt.amount = 10 THEN account_move_line.balance ELSE 0 END)
                ) *
                    (CASE WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN 1 ELSE -1 END)
                    AS gravado_10,
                
                (
                    --SUM(CASE WHEN bt.l10n_xma_tax_factor_type_id = 9 AND bt.amount = 5 THEN account_move_line.balance ELSE 0 END) +
                    SUM(CASE WHEN nt.l10n_xma_tax_factor_type_id = 9 AND nt.amount = 5 THEN account_move_line.balance ELSE 0 END)
                ) *
                    (CASE WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN 1 ELSE -1 END)
                    AS gravado_5,
                
                -- Total comprobante
                CASE
                    WHEN account_move.move_type IN ('in_invoice', 'in_refund') THEN -account_move.amount_total_signed
                    ELSE account_move.amount_total_signed
                END AS total_comprobante,
                               
                -- Campos adicionales
                CASE
                    WHEN account_move.l10n_xma_payment_term = 'cash' THEN '1'
                    WHEN account_move.l10n_xma_payment_term = 'credit' THEN '2'
                    ELSE ''
                END AS condicion_compra_codigo,
                CASE
                    WHEN account_move.currency_id != res_company.currency_id THEN 'S'
                    ELSE 'N'
                END AS moneda_extranjera,
                'S' AS imputa_iva,
                'N' AS imputa_ire,
                'N' AS imputa_irp_rsp,
                'N' AS no_imputa,
                CASE
                    WHEN account_move.move_type IN ('out_refund', 'in_refund') AND account_move.reversed_entry_id IS NOT NULL THEN
                        (SELECT name FROM account_move am2 WHERE am2.id = account_move.reversed_entry_id)
                    WHEN account_move.debit_origin_id IS NOT NULL THEN
                        (SELECT name FROM account_move am3 WHERE am3.id = account_move.debit_origin_id)
                    ELSE ''
                END AS comprobante_venta_numero,
                account_move.l10n_xma_number_timbrado_asociado AS timbrado_venta
            FROM
                %(table_references)s
                JOIN account_move ON account_move_line.move_id = account_move.id
                JOIN res_company ON account_move.company_id = res_company.id
                JOIN account_journal ON account_move.journal_id = account_journal.id
                LEFT JOIN account_tax AS nt ON account_move_line.tax_line_id = nt.id
                LEFT JOIN res_partner AS rp ON account_move.commercial_partner_id = rp.id
                LEFT JOIN l10n_latam_document_type AS ldt ON account_move.l10n_latam_document_type_id = ldt.id
                LEFT JOIN l10n_latam_identification_type AS lit ON rp.l10n_latam_identification_type_id = lit.id
                LEFT JOIN account_move_line_account_tax_rel AS amltr ON account_move_line.id = amltr.account_move_line_id
                LEFT JOIN account_tax AS bt ON amltr.account_tax_id = bt.id
            WHERE
                ldt.code <> '5' AND ldt.code <> '6' AND ldt.code <> '9'
                AND (nt.type_tax_use IN %(tax_types)s OR bt.type_tax_use IN %(tax_types)s)
                %(search_condition)s
            GROUP BY
                account_move.id, lit.id, rp.id, ldt.id, res_company.id
            ORDER BY
                account_move.invoice_date, account_move.name
        """,
        column_group_key=column_group_key,
        table_references=table_references,
        tax_types=tax_types,
        search_condition=search_condition,)