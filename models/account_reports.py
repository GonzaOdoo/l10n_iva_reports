from odoo import models
import markupsafe
import logging

_logger= logging.getLogger(__name__)

class AccountReportFootnote(models.Model):
    _inherit = 'account.report'
    
    def _get_pdf_export_html(self, options, lines, additional_context=None, template=None):
        report_info = self.get_report_information(options)
        custom_print_templates = report_info['custom_display'].get('pdf_export', {})
        template = custom_print_templates.get('pdf_export_main', 'account_reports.pdf_export_main')
        _logger.info(options)
        # Determinar el título del reporte
        if 'py_vat_book_tax_types_available' in options:
            _logger.info(options['py_vat_book_tax_types_available'])
            title = ''
            if options['py_vat_book_tax_types_available']['purchase']['selected'] == True:
                title += 'COMPRAS '
            if options['py_vat_book_tax_types_available']['sale']['selected'] == True:
                title += 'VENTAS'
            report_title = f"LIBRO {title} LEY 125/91"
        else:
            report_title = self.name
        
        render_values = {
            'report': self,
            'report_title': report_title,  # Usamos el título condicional aquí
            'options': options,
            'table_start': markupsafe.Markup('<tbody>'),
            'table_end': markupsafe.Markup('''
                </tbody></table>
                <div style="page-break-after: always"></div>
                <table class="o_table table-hover">
            '''),
            'column_headers_render_data': self._get_column_headers_render_data(options),
            'custom_templates': custom_print_templates,
        }
        if additional_context:
            render_values.update(additional_context)

        if options.get('order_column'):
            lines = self.sort_lines(lines, options)

        lines = self._format_lines_for_display(lines, options)

        render_values['lines'] = lines

        # Manage annotations.
        render_values['annotations'] = self._build_annotations_list_for_pdf_export(options['date'], lines, report_info['annotations'])

        options['css_custom_class'] = report_info['custom_display'].get('css_custom_class', '')

        # Render.
        return self.env['ir.qweb']._render(template, render_values)