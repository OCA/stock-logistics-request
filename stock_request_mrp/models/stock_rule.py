# Copyright 2020-24 ForgeFlow S.L. (https://www.forgeflow.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import Command, api, models


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _prepare_mo_vals(
        self,
        product_id,
        product_qty,
        product_uom,
        location_dest_id,
        name,
        origin,
        company_id,
        values,
        bom,
    ):
        res = super()._prepare_mo_vals(
            product_id,
            product_qty,
            product_uom,
            location_dest_id,
            name,
            origin,
            company_id,
            values,
            bom,
        )
        if "stock_request_id" in values:
            res["stock_request_ids"] = [(4, values["stock_request_id"])]
        return res

    @api.model
    def _run_manufacture(self, procurements):
        res = super()._run_manufacture(procurements)
        requests = self.env["stock.request"].sudo()
        for procurement, rule in procurements:
            # With sudo: the user that confirms may not read the productions
            request = requests.browse(procurement.values.get("stock_request_id"))
            if not request or request.production_ids:
                continue
            # The procurement was added to an existing manufacturing order
            bom = rule._get_matching_bom(
                procurement.product_id, procurement.company_id, procurement.values
            )
            production = (
                self.env["mrp.production"]
                .sudo()
                .search(rule._make_mo_get_domain(procurement, bom), limit=1)
            )
            if production:
                production.stock_request_ids = [Command.link(request.id)]
                request._update_production_allocations()
        return res
