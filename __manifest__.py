# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Paraguay Accounting Reports',
    'version': '1.0',
    'author': 'GonzaOdoo',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Reporting for Paraguay Xmarts Localization',
    'description': """
* Implementa el Libro de IVA requerido por la SET (Subsecretaría de Estado de Tributación) de Paraguay, que contiene el detalle de las operaciones gravadas con IVA en un período determinado.
* Incluye un reporte resumen de IVA para análisis de facturación
* Funcionalidades principales:

    * Libro de Ventas con detalle de IVA
    * Libro de Compras con detalle de IVA
    * Clasificación por tasas de IVA (5% y 10%)
    * Registro de documentos fiscales con timbrado
    * Reporte de operaciones exentas y no gravadas

Base Legal:

* Ley N° 125/91 - Código Tributario
* Resolución General N° 44/2019 de la SET - Normativa sobre registros contables
* Requisitos de facturación electrónica y registros digitales

Características técnicas:

* Integración con documentos fiscales electrónicos
* Compatibilidad con el sistema de facturación electrónica de Paraguay
* Generación de reportes en formatos compatibles con los requerimientos de la SET
""",
    'depends': [
        'l10n_xma_einvoice_py',
        'account_reports',
        'account',
    ],
    'data': [
        'data/account_financial_report_data.xml',
        'data/ir_sequence.xml',
        'views/account_move_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_iva_reports/static/src/components/**/*',
        ],
    },
    'auto_install': False,
    'installable': True,
    'license': 'OEEL-1',
}
