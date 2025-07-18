from odoo import api, models, fields, _
from odoo.tools import SQL
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)
class ParaguayVATCSVReportHandler(models.AbstractModel):
    _name = 'l10n_py.vat.csv.report.handler'
    _inherit = 'account.tax.report.handler'
    _description = 'Paraguay VAT CSV Report Custom Handler'

    def _get_custom_display_config(self):
        parent_config = super()._get_custom_display_config()
        parent_config['templates']['AccountReportFilters'] = 'l10n_iva_reports.L10nPyReportsFiltersCustomizable'
        return parent_config

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        move_info_dict = {}
        total_values_dict = {}

        # Campos numéricos que se mostrarán como números
        number_keys = ['gravado_10', 'gravado_5', 'exento', 'total_comprobante']

        query_list = []
        options_per_col_group = report._split_options_per_column_group(options)
        for column_group_key, column_group_options in options_per_col_group.items():
            query = self._build_query(report, column_group_options, column_group_key)
            query_list.append(SQL("(%s)", query))
            total_values_dict.setdefault(column_group_key, dict.fromkeys(number_keys, 0.0))

        full_query = SQL(" UNION ALL ").join(query_list)
        self._cr.execute(full_query)
        results = self._cr.dictfetchall()

        # Procesar resultados
        for result in results:
            move_id = result['id']
            column_group_key = result['column_group_key']
            result['fecha_emision'] = result['fecha_emision'].strftime("%d/%m/%Y") if result.get('fecha_emision') else ''

            current_move_info = move_info_dict.setdefault(move_id, {})
            current_move_info['line_name'] = self._format_line_name(result)
            current_move_info[column_group_key] = result

            totals = total_values_dict[column_group_key]
            for key in number_keys:
                totals[key] += result.get(key, 0.0)

        lines = []
        for move_id, move_info in move_info_dict.items():
            line = self._create_report_line(report, options, move_info, move_id, number_keys)
            lines.append((0, line))

        # Manejar límite de líneas para vista previa
        if not options['export_mode'] and len(lines) > (report.load_more_limit or 0):
            if warnings is not None:
                warnings['l10n_py_reports.skipped_lines_warning'] = {}
            lines_to_hide = lines[report.load_more_limit:]
            lines = lines[:report.load_more_limit]

            col_indices_to_sum = [
                i for i, col_data in enumerate(options['columns'])
                if col_data['expression_label'] in number_keys
            ]

            column_sums = defaultdict(float)
            for _line_sequence, line in lines_to_hide:
                for col_index in col_indices_to_sum:
                    column_sums[col_index] += line['columns'][col_index]['no_format']

            lines.append((0, {
                'id': report._get_generic_line_id(None, None, markup='placeholder'),
                'name': _("+%s non-previewed lines", len(lines_to_hide)),
                'columns': [
                    {
                        'class': 'number',
                        'no_format': column_sums[col_index],
                        'name': report.format_value(options_per_col_group[col['column_group_key']], column_sums[col_index], figure_type='monetary'),
                    } if col_index in column_sums else {}
                    for col_index, col in enumerate(options['columns'])
                ],
                'level': 2,
            }))

        # Línea de total si solo hay un tipo de diario seleccionado
        if len(self._vat_book_get_selected_tax_types(options)) < 2:
            lines.append((0, self._create_report_total_line(report, options, total_values_dict)))

        return lines

    def _format_line_name(self, result):
        """Formato personalizado para nombre de línea"""
        return f"{result.get('numero_timbrado', '')} - {result.get('numero_comprobante', '')}"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        csv_export_button = {
            'name': _('Exportar a CSV'),
            'sequence': 25,
            'action': 'export_file',
            'action_param': 'export_to_csv',  # Este debe coincidir con el nombre del método en tu handler
            'file_export_type': _('CSV'),
        }
    
        # Añadimos los botones
        options['buttons'].append(csv_export_button)
        # Configurar tipos de impuestos disponibles
        options['py_vat_book_tax_types_available'] = previous_options.get('py_vat_book_tax_types_available') or {
            'sale': {'name': 'Ventas', 'selected': False},
            'purchase': {'name': 'Compras', 'selected': True},
        }
        
        # Forzar dominio para documentos fiscales
        options['forced_domain'] = [
            *options.get('forced_domain', []),
            ('journal_id.l10n_latam_use_documents', '!=', False),
        ]

    def _build_query(self, report, options, column_group_key) -> SQL:
        query = report._get_report_query(options, 'strict_range')
        tax_types = tuple(self._vat_book_get_selected_tax_types(options))
        _logger.info(tax_types)
        # Aquí puedes usar otra consulta SQL específica para tu nuevo reporte
        return self.env['account.py.vat.csv.line']._py_vat_csv_line_build_query(
            query.from_clause,
            query.where_clause,
            column_group_key,
            tax_types
        )

    def _create_report_line(self, report, options, move_vals, move_id, number_values):
        columns = []
        for column in options['columns']:
            expression_label = column['expression_label']
            value = move_vals.get(column['column_group_key'], {}).get(expression_label)
            columns.append(report._build_column_dict(value, column, options=options))

        return {
            'id': report._get_generic_line_id('account.move', move_id),
            'caret_options': 'account.move',
            'name': move_vals['line_name'],
            'columns': columns,
            'level': 2,
        }

    def _create_report_total_line(self, report, options, total_vals):
        columns = []
        for column in options['columns']:
            expression_label = column['expression_label']
            value = total_vals.get(column['column_group_key'], {}).get(expression_label)
            columns.append(report._build_column_dict(value, column, options=options))

        return {
            'id': report._get_generic_line_id(None, None, markup='total'),
            'name': _('Total'),
            'class': 'total',
            'level': 1,
            'columns': columns,
        }

    def _vat_book_get_selected_tax_types(self, options):
        selected_types = [
            selected_type_key
            for selected_type_key, selected_type_value in options.get('py_vat_book_tax_types_available', {}).items()
            if selected_type_value['selected']
        ]
        return selected_types if selected_types else ['sale', 'purchase']

    def _validate_period(self, options):
        date_options = options.get('date', {})
        mode = date_options.get('mode')
        if mode not in ['range', 'single']:
            raise UserError(_('Debe seleccionar un periodo válido (por mes o por año).'))
    
        if mode == 'range':
            # Es un rango de fechas, validamos si corresponde a un mes completo o a un año
            date_from = fields.Date.from_string(date_options.get('date_from'))
            date_to = fields.Date.from_string(date_options.get('date_to'))
    
            if date_from.month == date_to.month and date_from.year == date_to.year:
                # Es un mes completo
                return f"{date_from.month:02d}{date_from.year}"
            elif date_from.year == date_to.year and date_from.month == 1 and date_to.month == 12:
                # Es un año completo
                return str(date_from.year)
            else:
                raise UserError(_('El rango de fechas debe ser un mes completo o un año completo.'))
        elif mode == 'single':
            # Es una fecha única, tratamos como mes
            date = fields.Date.from_string(date_options.get('date'))
            return f"{date.month:02d}{date.year}"

    def _get_company_ruc(self, options):
        company_id = self.env.company
        vat = company_id.vat or ''
        # Quitar el último carácter (dígito verificador)
        return vat

    def _get_identifier(self, options):
        tax_types = self._vat_book_get_selected_tax_types(options)
    
        if len(tax_types) == 0:
            raise UserError(_('Debe seleccionar al menos un tipo de transacción (Ventas o Compras).'))
    
        if tax_types == ['purchase']:
            return 'C0001'
        elif tax_types == ['sale']:
            return 'V0001'
        else:
            return '00001'

    def export_to_csv(self, options):
        """Exporta los datos del reporte a un archivo CSV con formato RG90."""
        report = self.env.ref('l10n_iva_reports.l10n_py_vat_book_report')
    
        # Validar que haya un modo de fecha correcto
        period = self._validate_period(options)
        ruc = self._get_company_ruc(options)
        identifier = self._get_identifier(options)
    
        # Generar nombre base
        filename_base = f"{ruc}_REG_{period}_{identifier}"
        csv_filename = f"{filename_base}.csv"
        zip_filename = f"{filename_base}.zip"
    
        lines = self._dynamic_lines_generator(
            report=report,
            options=options,
            all_column_groups_expression_totals={}
        )
    
        # Extraer líneas reales
        data_lines = [line for line in lines if isinstance(line, tuple) and line[0] == 0 and not line[1].get('markup')]
    
        # Encabezados oficiales
        headers = [
            'CÓDIGO TIPO DE REGISTRO',
            'CÓDIGO TIPO DE IDENTIFICACIÓN DEL PROVEEDOR/VENDEDOR',
            'NÚMERO DE IDENTIFICACIÓN DEL PROVEEDOR/VENDEDOR',
            'NOMBRE O RAZÓN SOCIAL DEL PROVEEDOR/VENDEDOR',
            'CÓDIGO TIPO DE COMPROBANTE',
            'FECHA DE EMISIÓN DEL COMPROBANTE',
            'NÚMERO DE TIMBRADO',
            'NÚMERO DEL COMPROBANTE',
            'MONTO GRAVADO AL 10%',
            'MONTO GRAVADO AL 5%',
            'MONTO EXENTO',
            'TOTAL DEL COMPROBANTE',
            'CONDICIÓN DE COMPRA',
            'OPERACIÓN EN MONEDA EXTRANJERA',
            'IMPUTA AL IVA',
            'IMPUTA AL IRE',
            'IMPUTA AL IRP-RSP',
            'NO IMPUTA',
            'NÚMERO DEL COMPROBANTE DE VENTA ASOCIADO',
            'TIMBRADO DEL COMPROBANTE DE VENTA ASOCIADO'
        ]
    
        expression_labels = {col['expression_label']: idx for idx, col in enumerate(options['columns'])}
    
        rows = []
        for line in data_lines:
            row_data = line[1]
            columns = row_data.get('columns', [])
            row = [''] * len(headers)
    
            for col in columns:
                expr_label = col.get('expression_label')
                no_format = col.get('no_format', '')
                value = '' if no_format is None else str(no_format).strip()
                if expr_label in expression_labels:
                    idx = expression_labels[expr_label]
                    row[idx] = value
    
            rows.append(row)
    
        # Construimos el CSV
        import csv
        from io import StringIO
        from zipfile import ZipFile
        from base64 import b64encode
        import tempfile
    
        output = StringIO()
        writer = csv.writer(output, delimiter=';', lineterminator='\r\n')
        #writer.writerow(headers)
        writer.writerows(rows)
        csv_content = output.getvalue().encode('utf-8-sig')
    
        # Crear ZIP
        temp_zip = tempfile.SpooledTemporaryFile()
        with ZipFile(temp_zip, mode='w') as zip_file:
            zip_file.writestr(csv_filename, csv_content)
    
        temp_zip.seek(0)
        zip_content = temp_zip.read()
    
        return {
            'file_name': zip_filename,
            'file_content': zip_content,
            'file_type': 'zip',
        }