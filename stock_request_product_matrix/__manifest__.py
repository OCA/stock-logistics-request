# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Stock Request Product Matrix",
    "summary": "Use a product matrix to efficiently request product variants",
    "category": "Warehouse Management",
    "version": "19.0.1.0.0",
    "license": "AGPL-3",
    "author": "ACSONE SA/NV,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-request",
    "depends": [
        "stock_request",
        "product_matrix",
    ],
    "data": [
        "views/stock_request_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_request_product_matrix/static/src/**/*",
        ],
    },
    "installable": True,
}
