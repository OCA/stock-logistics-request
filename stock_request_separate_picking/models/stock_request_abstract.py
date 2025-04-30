# Copyright 2023 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class StockRequestAbstract(models.AbstractModel):
    _inherit = "stock.request.abstract"

    procurement_group_id = fields.Many2one(
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)

        if not self.env.company.stock_request_allow_separate_picking:
            return requests

        requests_no_group = requests.filtered(
            lambda request: not request.procurement_group_id
        )
        if not requests_no_group:
            return requests

        ProcurementGroup = self.env["procurement.group"]

        for request in requests:
            if request.order_id:
                request.procurement_group_id = request.order_id.procurement_group_id
            else:
                request.procurement_group_id = ProcurementGroup.create(
                    {"name": request.name}
                )
        return requests
