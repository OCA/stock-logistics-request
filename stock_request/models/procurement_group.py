# Copyright (C) 2019 Open Source Integrators
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, models


class StockRule(models.Model):
    _inherit = "stock.rule"

    @api.model
    def run(self, procurements, raise_user_error=True):
        """Override to update the origin with the stock request order name."""
        new_procs = []
        for procurement in procurements:
            if "stock_request_id" in procurement.values and procurement.values.get(
                "stock_request_id"
            ):
                req = self.env["stock.request"].browse(
                    procurement.values.get("stock_request_id")
                )
                if req.order_id:
                    # Replace the origin with the order name
                    new_procs.append(procurement._replace(origin=req.order_id.name))
                else:
                    new_procs.append(procurement)
            else:
                new_procs.append(procurement)
        return super().run(new_procs, raise_user_error=raise_user_error)
