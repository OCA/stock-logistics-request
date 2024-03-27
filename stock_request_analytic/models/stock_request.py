# Copyright 2017-2020 ForgeFlow, S.L. (https://www.forgeflow.com)
# Copyright 2021 Tecnativa - João Marques
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class StockRequest(models.Model):
    _name = "stock.request"
    _inherit = ["stock.request", "analytic.mixin"]
    _check_company_auto = True

    analytic_distribution = fields.Json(
        copy=True,
        readonly=False,
    )

    def _prepare_procurement_values(self, group_id=False):
        """
        Add analytic distribution to procurement values
        """
        res = super()._prepare_procurement_values(group_id=group_id)
        if self.analytic_distribution:
            res.update({"analytic_distribution": self.analytic_distribution})
        return res
