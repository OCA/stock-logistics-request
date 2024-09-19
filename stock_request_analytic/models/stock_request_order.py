# Copyright 2018 Creu Blanca
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models


class StockRequestOrder(models.Model):
    _name = "stock.request.order"
    _inherit = ["analytic.mixin", "stock.request.order"]
