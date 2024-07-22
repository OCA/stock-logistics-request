# Copyright 2024 Jarsa (https://www.jarsa.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models


class StockRequest(models.Model):
    _inherit = "stock.request"

    lot_id = fields.Many2one("stock.lot", string="Lot/Serial Number")

    def _prepare_procurement_values(self, group_id=False):
        res = super()._prepare_procurement_values(group_id=group_id)
        res["restrict_lot_id"] = self.lot_id.id
        return res
