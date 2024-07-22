# Copyright 2024 Jarsa (https://www.jarsa.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

{
    "name": "Stock Request Lot",
    "summary": "Add lot to stock request",
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
    "website": "https://github.com/OCA/stock-logistics-request",
    "author": "Jarsa, Odoo Community Association (OCA)",
    "category": "Warehouse Management",
    "depends": ["stock_request", "stock_restrict_lot"],
    "data": [
        "views/stock_request_views.xml",
        "views/stock_request_order_views.xml",
    ],
    "installable": True,
    "auto_install": True,
}
