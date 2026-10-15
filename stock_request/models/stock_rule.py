# Copyright 2017-2020 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, models


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_stock_move_values(
        self,
        product_id,
        product_qty,
        product_uom,
        location_id,
        name,
        origin,
        company_id,
        values,
    ):
        result = super()._get_stock_move_values(
            product_id,
            product_qty,
            product_uom,
            location_id,
            name,
            origin,
            company_id,
            values,
        )
        if values.get("stock_request_id", False):
            result["allocation_ids"] = [
                (
                    0,
                    0,
                    {
                        "stock_request_id": values.get("stock_request_id"),
                        "requested_product_uom_qty": product_qty,
                    },
                )
            ]
        return result

    @api.model
    def run(self, procurements, raise_user_error=True):
        indexes_to_pop = []
        new_procs = []
        for i, procurement in enumerate(procurements):
            if "stock_request_id" in procurement.values and procurement.values.get(
                "stock_request_id"
            ):
                req = self.env["stock.request"].browse(
                    procurement.values.get("stock_request_id")
                )
                if req.order_id:
                    new_procs.append(procurement._replace(origin=req.order_id.name))
                    indexes_to_pop.append(i)
        if new_procs:
            indexes_to_pop.reverse()
            for index in indexes_to_pop:
                procurements.pop(index)
            procurements.extend(new_procs)
        return super().run(procurements, raise_user_error=raise_user_error)
