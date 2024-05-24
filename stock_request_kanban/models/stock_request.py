# Copyright 2018 Creu Blanca
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models


class StockRequest(models.Model):
    _inherit = "stock.request"

    kanban_id = fields.Many2one("stock.request.kanban", readonly=True)

    def action_scan_kanban(self):
        return {
            "res_model": "wizard.stock.request.kanban",
            "views": [[False, "form"]],
            "target": "new",
            "type": "ir.actions.act_window",
            "context": self._context,
        }
