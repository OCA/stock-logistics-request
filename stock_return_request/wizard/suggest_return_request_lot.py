# Copyright 2020 Tecnativa - David Vidal
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class SuggestReturnRequestLot(models.TransientModel):
    _name = "suggest.return.request.lot"
    _description = "Suggest lots for the return request line"

    request_line_id = fields.Many2one(
        comodel_name="stock.return.request.line",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    lot_suggestion_mode = fields.Selection(
        selection=[
            ("sum", "Total by lot"),
            ("detail", "Total by move"),
        ],
        default="sum",
    )
    suggested_lot_id = fields.Many2one("suggest.return.request.lot.line")

    @api.onchange("lot_suggestion_mode")
    def _onchange_lot_suggestion_mode(self):
        self.suggested_lot_id = False

    def action_confirm(self):
        self.request_line_id.lot_id = self.suggested_lot_id.lot_id.id


class SuggestReturnRequestLotLine(models.TransientModel):
    _name = "suggest.return.request.lot.line"
    _description = "Suggest lots for the return request line"

    wizard_id = fields.Many2one(
        comodel_name="suggest.return.request.lot",
        ondelete="cascade",
    )
    lot_id = fields.Many2one(comodel_name="stock.lot")
    name = fields.Char()
    lot_suggestion_mode = fields.Selection(
        selection=[
            ("sum", "Total by lot"),
            ("detail", "Total by move"),
        ]
    )
