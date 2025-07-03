from odoo import api, models, _
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
        _logger.info(query.where_clause,)
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