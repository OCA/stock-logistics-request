# Copyright 2017-2020 ForgeFlow, S.L. (https://www.forgeflow.com)
# Copyright 2021 Tecnativa - João Marques
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class StockRequest(models.Model):
    _name = "stock.request"
    _inherit = ["analytic.mixin", "stock.request"]

    analytic_distribution = fields.Json(compute="_compute_analytic_distribution")

    @api.depends("order_id")
    def _compute_analytic_distribution(self):
        """Set default analytic distribution on lines from order if defined"""
        for req in self:
            if req.order_id.analytic_distribution:
                req.analytic_distribution = req.order_id.analytic_distribution

    def _prepare_procurement_values(self, group_id=False):
        """
        Add analytic distribution to procurement values
        """
        res = super()._prepare_procurement_values(group_id=group_id)
        if self.analytic_distribution:
            res.update({"analytic_distribution": self.analytic_distribution})
        return res
