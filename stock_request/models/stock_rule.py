# Copyright 2017-2020 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import models


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

    def _run_push(self, move):
        """The pushed move takes over the allocations of the original move, up
        to the quantity moved. A request that gets nothing keeps its allocation
        on the original move with no requested quantity, so that it is
        cancelled instead of staying open."""
        new_move = super()._run_push(move)
        if (
            new_move
            and move.allocation_ids
            and move._stock_request_before_final_location()
        ):
            new_move._stock_request_fit_allocations()
            allocations = move.allocation_ids.sudo()
            pushed_requests = new_move.allocation_ids.stock_request_id
            pushed = allocations.filtered(
                lambda a: a.stock_request_id in pushed_requests
            )
            pushed.unlink()
            (allocations - pushed).write({"requested_product_uom_qty": 0.0})
        return new_move
